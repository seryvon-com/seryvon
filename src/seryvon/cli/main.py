# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Command-line interface (Typer).

`seryvon run <url>` crawls the site and emits a report (JSON/HTML/Markdown);
`seryvon aso <url>` audits only the ASO pillar (module M11); `seryvon history
<host>` reloads the persisted audits. `compare`, `ci` (document 02, §3.1) remain
skeletons to fix the CLI surface. User-facing help and output stay in French.
"""

from __future__ import annotations

import asyncio
import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from seryvon import __version__
from seryvon.citation import (
    AnthropicConnector,
    GeminiConnector,
    LlmConnector,
    OpenAiConnector,
    PerplexityConnector,
    estimate_cost,
    generate_prompt_set,
    run_tracking,
)
from seryvon.core.audit import run_audit
from seryvon.core.config import AuditConfig, Settings, get_settings
from seryvon.crawler import crawl_site, discover
from seryvon.db import repository
from seryvon.db.base import session_scope
from seryvon.models.enums import Status
from seryvon.models.prompts import PromptSet
from seryvon.models.report import AuditReport
from seryvon.models.signals import CitationMetrics, SignalBundle
from seryvon.reporting import report_to_html, report_to_json, report_to_markdown, report_to_pdf


class OutputFormat(StrEnum):
    """Format(s) de sortie du rapport d'audit."""

    json = "json"
    html = "html"
    md = "md"
    pdf = "pdf"
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
    """Force stdout/stderr to UTF-8 (Windows cp1252 consoles: FR characters, ≥, —)."""
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
        report, pages = asyncio.run(run_audit(url, audit_config))
    except Exception as exc:
        console.print(f"[red]Échec de l'audit :[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _write_report(report, output, fmt, quiet=quiet)

    if persist:
        with session_scope() as session:
            audit_id = repository.persist_report(report, session)
            repository.persist_pages(audit_id, pages, session)
        if not quiet:
            console.print(f"[green]Audit persisté :[/green] {audit_id}")

    if not quiet:
        _print_summary(report)


def _write_report(
    report: AuditReport, output: Path | None, fmt: OutputFormat, *, quiet: bool
) -> None:
    """Write the report in the requested format(s), to a file or stdout."""
    text_renderers = {
        OutputFormat.json: report_to_json,
        OutputFormat.html: report_to_html,
        OutputFormat.md: report_to_markdown,
    }

    if output is None:
        if quiet:
            # PDF cannot be emitted on stdout; fall back to JSON.
            renderer = text_renderers.get(fmt, report_to_json)
            typer.echo(renderer(report))
        return

    if fmt is OutputFormat.both:
        text_targets: dict[Path, Any] = {
            output.with_suffix(".json"): report_to_json,
            output.with_suffix(".html"): report_to_html,
        }
        for path, render in text_targets.items():
            path.write_text(render(report), encoding="utf-8")
        written_paths = list(text_targets)
    elif fmt is OutputFormat.pdf:
        try:
            pdf_bytes = report_to_pdf(report)
        except ImportError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        pdf_path = output.with_suffix(".pdf")
        pdf_path.write_bytes(pdf_bytes)
        written_paths = [pdf_path]
    else:
        path = output
        path.write_text(text_renderers[fmt](report), encoding="utf-8")
        written_paths = [path]

    if not quiet:
        written = ", ".join(str(p) for p in written_paths)
        console.print(f"[green]Rapport écrit :[/green] {written}")


def _print_summary(report) -> None:  # type: ignore[no-untyped-def]
    """Print a readable summary of the per-pillar scores."""
    table = Table(title=f"Audit — {report.domain}")
    table.add_column("Pilier")
    table.add_column("Score", justify="right")
    table.add_column("Mesurés", justify="right")
    table.add_column("Exclus", justify="right")
    table.add_column("Couv.", justify="right")
    for pillar, ps in report.pillars.items():
        table.add_row(
            pillar.upper(),
            f"{ps.score:.1f}",
            str(ps.measured),
            str(ps.excluded),
            f"{ps.coverage * 100:.0f}%",
        )
    console.print(table)
    console.print(
        f"[bold]Score global :[/bold] {report.score_global:.1f} "
        f"· couverture {report.coverage * 100:.0f}%"
    )


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
        report, _pages = asyncio.run(run_audit(url, audit_config))
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
    """ASO subset of the report (focused, deterministic view)."""
    readiness = report.aso_readiness
    return {
        "domain": report.domain,
        "tool_version": report.tool_version,
        "aso": report.pillars["aso"].model_dump(mode="json"),
        "aso_readiness": readiness.model_dump(mode="json") if readiness else None,
        "criteria": [c.model_dump(mode="json") for c in report.criteria if "aso" in c.pillars],
    }


def _aso_json(report: AuditReport) -> str:
    """Serialize the ASO view to JSON (FR characters preserved, stable keys)."""
    return json.dumps(_aso_payload(report), ensure_ascii=False, indent=2)


def _print_aso_summary(report: AuditReport) -> None:
    """Print the agentic-readiness card then the ASO pillar criteria."""
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
def citations(
    url: Annotated[str, typer.Argument(help="URL à auditer (citation LLM, module M4).")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Fichier de sortie JSON (sinon affichage console)."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Fichier YAML de configuration."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Génère le prompt set et estime le volume, sans rien envoyer."
        ),
    ] = False,
    repetitions: Annotated[
        int,
        typer.Option("--repetitions", "-k", help="Répétitions par (prompt, moteur)."),
    ] = 5,
    prompts: Annotated[
        int,
        typer.Option("--prompts", help="Taille cible du jeu de prompts."),
    ] = 15,
    competitors: Annotated[
        str | None,
        typer.Option(
            "--competitors", help="Concurrents à suivre (domaines séparés par des virgules)."
        ),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="N'émet que le JSON (pas de récapitulatif)."),
    ] = False,
) -> None:
    """Suivi de citation LLM (M4) : crawle le site, génère le prompt set, mesure la citation.

    `--dry-run` n'envoie aucun appel (prompt set + volume + coût estimés). Sinon, au
    moins une clé BYOK est requise parmi PERPLEXITY/OPENAI/ANTHROPIC/GEMINI_API_KEY.
    """
    audit_config = AuditConfig.from_yaml(config) if config else AuditConfig.default()
    competitor_list = [c.strip() for c in (competitors or "").split(",") if c.strip()]

    if not dry_run and not _configured_engines(get_settings()):
        console.print(
            "[yellow]Aucune clé LLM (PERPLEXITY/OPENAI/ANTHROPIC/GEMINI_API_KEY). "
            "Utilisez --dry-run ou configurez une clé.[/yellow]"
        )
        raise typer.Exit(code=2)

    try:
        payload = asyncio.run(
            _run_citations(
                url,
                audit_config,
                repetitions=repetitions,
                prompt_size=prompts,
                competitors=competitor_list,
                dry_run=dry_run,
            )
        )
    except Exception as exc:
        console.print(f"[red]Échec du suivi de citation :[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if output is not None:
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if not quiet:
            console.print(f"[green]Rapport citation écrit :[/green] {output}")
    elif quiet:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))

    if not quiet:
        _print_citations_summary(payload, dry_run=dry_run)


SUPPORTED_ENGINES: tuple[str, ...] = ("perplexity", "openai", "anthropic", "gemini")
_DEFAULT_DRY_RUN_ENGINE = "perplexity"


def _configured_engines(settings: Settings) -> list[str]:
    """Engines with a configured BYOK key, in canonical order."""
    keys = {
        "perplexity": settings.perplexity_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "gemini": settings.gemini_api_key,
    }
    return [engine for engine in SUPPORTED_ENGINES if keys.get(engine)]


def _build_connectors(settings: Settings) -> list[LlmConnector]:
    """Instantiate a connector for each configured engine (canonical order)."""
    connectors: list[LlmConnector] = []
    if settings.perplexity_api_key:
        connectors.append(PerplexityConnector(settings.perplexity_api_key))
    if settings.openai_api_key:
        connectors.append(OpenAiConnector(settings.openai_api_key))
    if settings.anthropic_api_key:
        connectors.append(AnthropicConnector(settings.anthropic_api_key))
    if settings.gemini_api_key:
        connectors.append(GeminiConnector(settings.gemini_api_key))
    return connectors


async def _run_citations(
    url: str,
    config: AuditConfig,
    *,
    repetitions: int,
    prompt_size: int,
    competitors: list[str],
    dry_run: bool,
) -> dict[str, Any]:
    """Crawl the site, build the prompt set, and (unless dry-run) run the tracking."""
    settings = get_settings()
    user_agent = config.crawl.user_agent or settings.user_agent
    discovery = await discover(
        url,
        user_agent=user_agent,
        timeout=settings.request_timeout,
        respect_robots=config.crawl.respect_robots,
    )
    pages = await crawl_site(
        discovery,
        user_agent=user_agent,
        max_pages=config.crawl.max_pages,
        max_depth=config.crawl.max_depth,
        respect_robots=config.crawl.respect_robots,
        timeout=settings.request_timeout,
    )
    bundle = SignalBundle(domain=discovery.domain, pages=pages)
    prompt_set = generate_prompt_set(bundle, target_size=prompt_size, competitors=competitors)

    if dry_run:
        engines = _configured_engines(settings) or [_DEFAULT_DRY_RUN_ENGINE]
        return _dry_run_payload(prompt_set, repetitions, engines)

    engines = _configured_engines(settings)
    connectors = _build_connectors(settings)
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        metrics = await run_tracking(
            prompt_set,
            connectors,
            target_domain=bundle.domain,
            brand=prompt_set.theme_profile.brand,
            competitors=competitors,
            repetitions=repetitions,
            client=client,
        )
    return _citation_payload(prompt_set, metrics, engines)


def _prompt_rows(prompt_set: PromptSet) -> list[dict[str, str]]:
    return [{"intent": p.intent.value, "text": p.text} for p in prompt_set.prompts]


def _dry_run_payload(prompt_set: PromptSet, repetitions: int, engines: list[str]) -> dict[str, Any]:
    cost = estimate_cost(engines, len(prompt_set.prompts), repetitions)
    return {
        "domain": prompt_set.domain,
        "dry_run": True,
        "engines": list(engines),
        "repetitions": repetitions,
        "prompt_count": len(prompt_set.prompts),
        "call_volume": len(prompt_set.prompts) * repetitions * len(engines),
        "cost_estimate": cost.model_dump(mode="json"),
        "theme_profile": prompt_set.theme_profile.model_dump(mode="json"),
        "prompts": _prompt_rows(prompt_set),
        "tracked_competitors": prompt_set.tracked_competitors,
    }


def _citation_payload(
    prompt_set: PromptSet, metrics: CitationMetrics | None, engines: list[str]
) -> dict[str, Any]:
    return {
        "domain": prompt_set.domain,
        "dry_run": False,
        "engines": list(engines),
        "prompt_set_version": prompt_set.version,
        "citation_metrics": metrics.model_dump(mode="json") if metrics else None,
        "prompts": _prompt_rows(prompt_set),
        "tracked_competitors": prompt_set.tracked_competitors,
    }


def _print_citations_summary(payload: dict[str, Any], *, dry_run: bool) -> None:
    """Print the prompt set/volume (dry-run) or the aggregated citation metrics."""
    if dry_run:
        console.print(
            f"[bold]Prompt set — {payload['domain']}[/bold] : "
            f"{payload['prompt_count']} prompt(s) × {payload['repetitions']} rép. × "
            f"{len(payload['engines'])} moteur(s) = {payload['call_volume']} appel(s) "
            "(dry-run, aucun appel envoyé)."
        )
        cost = payload.get("cost_estimate", {})
        note = " (indicatif)" if cost.get("indicative") else ""
        console.print(
            f"Coût estimé{note} : {cost.get('total', 0):.2f} {cost.get('currency', 'USD')}"
        )
        table = Table(title="Prompts générés")
        table.add_column("Intention")
        table.add_column("Prompt")
        for row in payload["prompts"]:
            table.add_row(row["intent"], row["text"])
        console.print(table)
        return

    metrics = payload.get("citation_metrics")
    if not metrics:
        console.print("[yellow]Aucune réponse exploitable : citation non mesurée.[/yellow]")
        return
    console.print(f"[bold]Citation LLM — {payload['domain']}[/bold]")
    console.print(
        f"Citation : {metrics['citation_rate'] * 100:.1f}% · "
        f"Mention : {metrics['mention_rate'] * 100:.1f}% · "
        f"Confiance : {metrics['citation_confidence'] * 100:.1f}%"
    )
    table = Table(title="Par moteur")
    table.add_column("Moteur")
    table.add_column("Citation", justify="right")
    table.add_column("Mention", justify="right")
    for engine, per in metrics.get("per_engine", {}).items():
        table.add_row(
            engine, f"{per['citation_rate'] * 100:.0f}%", f"{per['mention_rate'] * 100:.0f}%"
        )
    console.print(table)


@app.command()
def compare(
    url: Annotated[str, typer.Argument(help="URL de référence (gauche).")],
    competitor: Annotated[str, typer.Argument(help="URL à comparer (droite).")],
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Fichier YAML de configuration."),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="Mode de comparaison : strict | intersection | descriptive.",
        ),
    ] = "descriptive",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Fichier JSON de résultat (sinon stdout)."),
    ] = None,
) -> None:
    """Compare deux sites côte à côte (module M6 — comparaison de scorecards).

    Lance un audit complet sur chaque URL puis compare les scorecards selon
    le mode demandé (descriptive par défaut — toujours autorisé).
    """
    from seryvon.scoring.comparison import ComparisonMode, IncomparableError, compare_scorecards

    audit_config = AuditConfig.from_yaml(config) if config else AuditConfig.default()

    try:
        comparison_mode = ComparisonMode(mode)
    except ValueError:
        console.print(f"[red]Mode invalide :[/red] {mode!r}  (strict | intersection | descriptive)")
        raise typer.Exit(code=1) from None

    console.print(f"[bold]Audit 1 :[/bold] {url}")
    try:
        left_report, _lpages = asyncio.run(run_audit(url, audit_config))
    except Exception as exc:
        console.print(f"[red]Échec de l'audit 1 :[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold]Audit 2 :[/bold] {competitor}")
    try:
        right_report, _rpages = asyncio.run(run_audit(competitor, audit_config))
    except Exception as exc:
        console.print(f"[red]Échec de l'audit 2 :[/red] {exc}")
        raise typer.Exit(code=1) from exc

    try:
        result = compare_scorecards(left_report, right_report, comparison_mode)
    except IncomparableError as exc:
        allowed = [m.value for m in exc.allowed_modes]
        console.print(
            f"[red]Comparaison impossible en mode {mode!r} :[/red]"
            f" profils {exc.comparability.value}. Modes autorisés : {allowed}"
        )
        raise typer.Exit(code=3) from exc

    if output:
        output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"[green]Résultat écrit :[/green] {output}")
    else:
        _print_comparison(left_report.domain, right_report.domain, result)


def _print_comparison(left_domain: str, right_domain: str, result: Any) -> None:
    from rich.text import Text

    def _delta_str(d: float | None) -> Text:
        if d is None:
            return Text("—", style="dim")
        sign = "+" if d >= 0 else ""
        color = "green" if d > 0 else "red" if d < 0 else "dim"
        return Text(f"{sign}{d:.1f}", style=color)

    console.print(
        f"\n[bold]Comparaison[/bold]  {left_domain} vs {right_domain}  "
        f"· comparabilité : [bold]{result.comparability.value}[/bold]"
    )
    if result.recomputed:
        console.print(
            f"  [dim]Scores recalculés sur {len(result.common_criteria)} critères communs[/dim]"
        )
    if result.profile_differences:
        console.print(
            f"  [dim]Différences de profil : {', '.join(result.profile_differences)}[/dim]"
        )

    # Global summary
    left_g = "—" if result.left_global is None else f"{result.left_global:.1f}"
    right_g = "—" if result.right_global is None else f"{result.right_global:.1f}"
    console.print(f"\n  Score global : {left_g} → {right_g}  Δ ", end="")
    console.print(_delta_str(result.global_delta))

    # Pillar table
    if result.pillars:
        table = Table(title="Par pilier")
        table.add_column("Pilier")
        table.add_column(left_domain[:20], justify="right")
        table.add_column("Δ", justify="right")
        table.add_column(right_domain[:20], justify="right")
        for pd in result.pillars:
            ls = "—" if pd.left_score is None else f"{pd.left_score:.1f}"
            rs = "—" if pd.right_score is None else f"{pd.right_score:.1f}"
            table.add_row(pd.pillar.upper(), ls, _delta_str(pd.delta), rs)
        console.print(table)

    # Top changed criteria
    changed = [c for c in result.criteria if c.delta is not None and c.delta != 0]
    changed.sort(key=lambda c: abs(c.delta or 0), reverse=True)
    if changed:
        table2 = Table(title=f"Critères les plus impactés (top {min(15, len(changed))})")
        table2.add_column("Critère")
        table2.add_column(left_domain[:20], justify="right")
        table2.add_column("Δ", justify="right")
        table2.add_column(right_domain[:20], justify="right")
        for c in changed[:15]:
            ls = "—" if c.left_score is None else f"{c.left_score:.0f}"
            rs = "—" if c.right_score is None else f"{c.right_score:.0f}"
            table2.add_row(c.key, ls, _delta_str(c.delta), rs)
        console.print(table2)


@app.command(name="recalc-scores")
def recalc_scores(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Affiche les changements sans écrire en base."),
    ] = False,
) -> None:
    """Recalcule les scores pilier et global de tous les audits historiques.

    Utile après un changement de formule de scoring (ex. ajout du facteur
    de couverture). Lit les criterion_result stockés en base et réécrit
    pillar_score + audit.score_global.
    """
    from sqlalchemy import select

    from seryvon import PILLARS
    from seryvon.db import models as m
    from seryvon.models.criterion import CriterionResult
    from seryvon.models.enums import Status
    from seryvon.scoring.engine import score_global, score_pillar

    updated = 0
    skipped = 0

    with session_scope() as session:
        audit_ids = session.scalars(select(m.Audit.id)).all()
        console.print(f"[bold]{len(audit_ids)} audit(s) trouvé(s)[/bold]")

        for audit_id in audit_ids:
            rows = session.scalars(
                select(m.CriterionResultRow).where(m.CriterionResultRow.audit_id == audit_id)
            ).all()
            if not rows:
                skipped += 1
                continue

            # Rebuild lightweight CriterionResult objects from DB rows
            criteria = [
                CriterionResult(
                    key=r.criterion_key,
                    pillars=r.pillars,
                    score=r.score,
                    status=Status(r.status),
                    weight=r.weight,
                )
                for r in rows
            ]

            new_pillar_scores = {p: score_pillar(p, criteria) for p in PILLARS}
            new_global = score_global(new_pillar_scores, AuditConfig.default())

            if dry_run:
                audit_row = session.get(m.Audit, audit_id)
                domain = audit_row.domain.host if audit_row and audit_row.domain else "?"
                console.print(f"  [dim]{audit_id}[/dim] {domain}")
                for p, ps in new_pillar_scores.items():
                    console.print(f"    {p}: score={ps.score:.1f} coverage={ps.coverage:.0%}")
                console.print(f"    global: {new_global:.1f}")
            else:
                # Update pillar_score rows
                ps_rows = session.scalars(
                    select(m.PillarScoreRow).where(m.PillarScoreRow.audit_id == audit_id)
                ).all()
                ps_by_pillar = {r.pillar: r for r in ps_rows}
                for p, ps in new_pillar_scores.items():
                    row = ps_by_pillar.get(p)
                    if row:
                        row.score = ps.score
                        row.coverage = ps.coverage
                        row.coverage_label = str(ps.coverage_label)
                        row.measured = ps.measured
                        row.excluded = ps.excluded
                        row.not_applicable = ps.not_applicable

                # Update audit global score
                audit_row = session.get(m.Audit, audit_id)
                if audit_row:
                    audit_row.score_global = new_global

            updated += 1

        if not dry_run:
            session.commit()

    verb = "à recalculer" if dry_run else "mis à jour"
    console.print(
        f"[green]✓[/green] {updated} audit(s) {verb}, {skipped} ignoré(s) (sans critères)."
    )


if __name__ == "__main__":
    app()
