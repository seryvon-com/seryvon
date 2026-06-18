# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Interface en ligne de commande (Typer).

Phase 0 : `seryvon run <url>` crawle la home et émet un rapport JSON (livrable
de jalon, document 06, Phase 0). Les commandes `aso`, `compare`, `history`, `ci`
(document 02, §3.1) sont déclarées en squelette pour fixer la surface CLI.
"""

from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from seryvon import __version__
from seryvon.core.audit import run_audit
from seryvon.core.config import AuditConfig
from seryvon.db import repository
from seryvon.db.base import session_scope
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
def aso(url: Annotated[str, typer.Argument(help="URL à auditer (ASO seul).")]) -> None:
    """Audit du pilier ASO seul (rapide, statique). — implémenté en Phase 2."""
    console.print("[yellow]Commande `aso` prévue en Phase 2 (module M11).[/yellow]")
    raise typer.Exit(code=2)


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
