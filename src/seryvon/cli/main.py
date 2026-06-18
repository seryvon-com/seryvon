# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Interface en ligne de commande (Typer).

`seryvon run <url>` crawle le site et émet un rapport (JSON/HTML/Markdown) ;
`seryvon aso <url>` n'audite que le pilier ASO (module M11) ; `seryvon history
<host>` relit les audits persistés. `compare`, `ci` (document 02, §3.1) restent
des squelettes pour fixer la surface CLI.
"""

from __future__ import annotations

import asyncio
import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from seryvon import __version__
from seryvon.core.audit import run_audit
from seryvon.core.config import AuditConfig
from seryvon.db import repository
from seryvon.db.base import session_scope
from seryvon.models.enums import Status
from seryvon.models.report import AuditReport
from seryvon.reporting import report_to_html, report_to_json, report_to_markdown


class OutputFormat(StrEnum):
    """Format(s) de sortie du rapport d'audit."""

    json = "json"
    html = "html"
    md = "md"
    both = "both"  # json + html


app = typer.Typer(
    name="seryvon",
    help="Audit déterministe SEO / GEO / GSO / AEO / ASO (open core).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"Seryvon {__version__}")
        raise typer.Exit


def _force_utf8_output() -> None:
    """Force stdout/stderr en UTF-8 (consoles Windows cp1252 : caractères FR, ≥, —)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


@app.callback()
def main(
    _version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Affiche la version."
        ),
    ] = False,
) -> None:
    """Point d'entrée global."""
    _force_utf8_output()


@app.command()
def run(
    url: Annotated[str, typer.Argument(help="URL du site à auditer.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Fichier de sortie JSON (sinon stdout)."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config", "-c", help="Fichier YAML de configuration (pondérations, seuils)."
        ),
    ] = None,
    fmt: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Format de sortie : json, html ou both."),
    ] = OutputFormat.json,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="N'émet que le rapport (pas de tableau récapitulatif)."),
    ] = False,
    persist: Annotated[
        bool,
        typer.Option("--persist", help="Persiste le rapport en base (PostgreSQL requis)."),
    ] = False,
) -> None:
    """Lance un audit sur une URL et produit un rapport (JSON et/ou HTML).

    Crawle le site (robots.txt + sitemaps + liens internes, dans les limites de
    la config) puis score les 5 piliers.
    """
    audit_config = AuditConfig.from_yaml(config) if config else AuditConfig.default()

    try:
        report = asyncio.run(run_audit(url, audit_config))
    except Exception as exc:
        console.print(f"[red]Échec de l'audit :[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _write_report(report, output, fmt, quiet=quiet)

    if persist:
        with session_scope() as session:
            audit_id = repository.persist_report(report, session)
        if not quiet:
            console.print(f"[green]Audit persisté :[/green] {audit_id}")

    if not quiet:
        _print_summary(report)


def _write_report(
    report: AuditReport, output: Path | None, fmt: OutputFormat, *, quiet: bool
) -> None:
    """Écrit le rapport au(x) format(s) demandé(s), sur fichier ou stdout."""
    renderers = {
        OutputFormat.json: report_to_json,
        OutputFormat.html: report_to_html,
        OutputFormat.md: report_to_markdown,
    }

    if output is None:
        if quiet:
            # `both` sur stdout : on émet le JSON (source de vérité).
            typer.echo(renderers.get(fmt, report_to_json)(report))
        return

    if fmt is OutputFormat.both:
        targets = {
            output.with_suffix(".json"): report_to_json,
            output.with_suffix(".html"): report_to_html,
        }
    else:
        targets = {output: renderers[fmt]}

    for path, render in targets.items():
        path.write_text(render(report), encoding="utf-8")

    if not quiet:
        written = ", ".join(str(p) for p in targets)
        console.print(f"[green]Rapport écrit :[/green] {written}")


def _print_summary(report) -> None:  # type: ignore[no-untyped-def]
    """Affiche un récapitulatif lisible des scores par pilier."""
    table = Table(title=f"Audit — {report.domain}")
    table.add_column("Pilier")
    table.add_column("Score", justify="right")
    table.add_column("Mesurés", justify="right")
    table.add_column("Exclus", justify="right")
    for pillar, ps in report.pillars.items():
        table.add_row(pillar.upper(), f"{ps.score:.1f}", str(ps.measured), str(ps.excluded))
    console.print(table)
    console.print(f"[bold]Score global :[/bold] {report.score_global:.1f}")


@app.command()
def history(
    host: Annotated[str, typer.Argument(help="Hôte du domaine (ex. example.com).")],
) -> None:
    """Affiche l'historique des audits persistés d'un domaine."""
    with session_scope() as session:
        summaries = repository.list_audits(session, host)
    if not summaries:
        console.print(f"Aucun audit persisté pour [bold]{host}[/bold].")
        return
    table = Table(title=f"Historique — {host}")
    table.add_column("Date")
    table.add_column("Score global", justify="right")
    table.add_column("ID")
    for summary in summaries:
        score = "—" if summary.score_global is None else f"{summary.score_global:.1f}"
        table.add_row(summary.started_at.strftime("%Y-%m-%d %H:%M"), score, str(summary.audit_id))
    console.print(table)


@app.command()
def aso(
    url: Annotated[str, typer.Argument(help="URL à auditer (pilier ASO seul).")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Fichier de sortie JSON (sinon affichage console)."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config", "-c", help="Fichier YAML de configuration (pondérations, seuils)."
        ),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="N'émet que le JSON ASO (pas de carte récapitulative)."),
    ] = False,
) -> None:
    """Audit du pilier ASO seul : aptitude agentique (WebMCP, actions, AI discovery).

    Réutilise le pipeline complet (crawl + scoring déterministe) puis ne présente
    que le pilier ASO et sa carte de readiness agentique (module M11, document 11).
    """
    audit_config = AuditConfig.from_yaml(config) if config else AuditConfig.default()

    try:
        report = asyncio.run(run_audit(url, audit_config))
    except Exception as exc:
        console.print(f"[red]Échec de l'audit :[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if output is not None:
        output.write_text(_aso_json(report), encoding="utf-8")
        if not quiet:
            console.print(f"[green]Rapport ASO écrit :[/green] {output}")
    elif quiet:
        typer.echo(_aso_json(report))

    if not quiet:
        _print_aso_summary(report)


def _aso_payload(report: AuditReport) -> dict[str, Any]:
    """Sous-ensemble ASO du rapport (vue focalisée, déterministe)."""
    readiness = report.aso_readiness
    return {
        "domain": report.domain,
        "tool_version": report.tool_version,
        "aso": report.pillars["aso"].model_dump(mode="json"),
        "aso_readiness": readiness.model_dump(mode="json") if readiness else None,
        "criteria": [c.model_dump(mode="json") for c in report.criteria if "aso" in c.pillars],
    }


def _aso_json(report: AuditReport) -> str:
    """Sérialise la vue ASO en JSON (caractères FR préservés, clés stables)."""
    return json.dumps(_aso_payload(report), ensure_ascii=False, indent=2)


def _print_aso_summary(report: AuditReport) -> None:
    """Affiche la carte de readiness agentique puis les critères du pilier ASO."""
    aso = report.pillars["aso"]
    readiness = report.aso_readiness

    if readiness is not None:
        card = Table(title=f"ASO — {report.domain}", show_header=False)
        card.add_column("Indicateur")
        card.add_column("Valeur")
        card.add_row("Readiness", readiness.readiness_level.value)
        card.add_row("Agent-ready", "oui" if readiness.agent_ready else "non")
        card.add_row("WebMCP", "oui" if readiness.has_webmcp else "non")
        card.add_row("Schéma d'action", "oui" if readiness.has_action_schema else "non")
        card.add_row("Endpoints AI discovery", str(readiness.ai_discovery_endpoints))
        card.add_row("NLWeb", "oui" if readiness.has_nlweb else "non")
        brand = readiness.brand_coherence_score
        card.add_row("Cohérence de marque", "—" if brand is None else f"{brand:.1f}")
        if readiness.blocked_agent_bots:
            card.add_row("Bots agents bloqués", ", ".join(readiness.blocked_agent_bots))
        console.print(card)

    table = Table(title="Critères ASO")
    table.add_column("Critère")
    table.add_column("Statut")
    table.add_column("Score", justify="right")
    for c in report.criteria:
        if "aso" not in c.pillars:
            continue
        score = "—" if c.status is Status.NOT_MEASURED else f"{c.score:.0f}"
        table.add_row(c.key, c.status.value, score)
    console.print(table)
    console.print(
        f"[bold]Score ASO :[/bold] {aso.score:.1f} ({aso.measured} mesurés, {aso.excluded} exclus)"
    )


@app.command()
def compare(
    url: Annotated[str, typer.Argument(help="URL de référence.")],
    competitor: Annotated[str, typer.Argument(help="URL concurrente.")],
) -> None:
    """Compare un site à un concurrent. — implémenté en Phase 4 (module M6)."""
    console.print("[yellow]Commande `compare` prévue en Phase 4 (module M6).[/yellow]")
    raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
