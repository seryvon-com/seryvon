# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Export Markdown du rapport (dérivé du JSON source de vérité).

Rendu déterministe : score global, scores par pilier, readiness agentique,
plan d'action priorisé (P1–P4) et détail des critères groupés par pilier.
"""

from __future__ import annotations

from seryvon.models.criterion import CriterionResult
from seryvon.models.report import AuditReport

_PILLAR_ORDER = ("seo", "geo", "gso", "aeo", "aso")


def _cell(value: object) -> str:
    """Échappe une valeur pour une cellule de tableau Markdown."""
    return str(value).replace("|", r"\|").replace("\n", " ")


def _pillar_table(report: AuditReport) -> list[str]:
    rows = ["| Pilier | Score | Mesurés | Exclus |", "|---|---:|---:|---:|"]
    for name, ps in report.pillars.items():
        score = f"{ps.score:.1f}" if ps.measured else "—"
        rows.append(f"| {name.upper()} | {score} | {ps.measured} | {ps.excluded} |")
    return rows


def _readiness_block(report: AuditReport) -> list[str]:
    aso = report.aso_readiness
    if aso is None:
        return []
    brand = "—" if aso.brand_coherence_score is None else f"{aso.brand_coherence_score:.0f}"
    blocked = ", ".join(aso.blocked_agent_bots) if aso.blocked_agent_bots else "aucun"
    return [
        "## Readiness agentique (ASO)",
        "",
        f"- **Niveau** : `{aso.readiness_level.value}` "
        f"(agent-ready : {'oui' if aso.agent_ready else 'non'})",
        f"- WebMCP : {'oui' if aso.has_webmcp else 'non'} · "
        f"schema d'action : {'oui' if aso.has_action_schema else 'non'}",
        f"- Endpoints AI discovery : {aso.ai_discovery_endpoints}/4 · "
        f"NLWeb : {'oui' if aso.has_nlweb else 'non'}",
        f"- Cohérence de marque : {brand} · bots d'agents bloqués : {blocked}",
        "",
    ]


def _issues_block(report: AuditReport) -> list[str]:
    if not report.issues:
        return ["## Plan d'action", "", "Aucun problème prioritaire détecté.", ""]
    lines = [
        f"## Plan d'action ({len(report.issues)} problèmes)",
        "",
        "| Priorité | Critère | Sévérité | Impact | Effort | Recommandation |",
        "|---|---|---|---:|---:|---|",
    ]
    for issue in report.issues:
        lines.append(
            f"| {issue.priority_bucket} | `{issue.criterion_key}` | {issue.severity.value} "
            f"| {issue.impact} | {issue.effort} | {_cell(issue.recommendation)} |"
        )
    lines.append("")
    return lines


def _criteria_block(report: AuditReport) -> list[str]:
    lines = ["## Détail des critères", ""]
    ordered = sorted(report.criteria, key=lambda c: c.key)
    for pillar in _PILLAR_ORDER:
        rows = [c for c in ordered if pillar in c.pillars]
        if not rows:
            continue
        lines += [
            f"### {pillar.upper()}",
            "",
            "| Critère | Statut | Score | Explication |",
            "|---|---|---:|---|",
        ]
        lines += [_criterion_row(c) for c in rows]
        lines.append("")
    return lines


def _criterion_row(criterion: CriterionResult) -> str:
    return (
        f"| `{criterion.key}` | {criterion.status.value} | {criterion.score:.1f} "
        f"| {_cell(criterion.explanation)} |"
    )


def report_to_markdown(report: AuditReport) -> str:
    """Rend un rapport d'audit en Markdown déterministe."""
    generated = (report.finished_at or report.started_at).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Audit Seryvon — {report.domain}",
        "",
        f"**Score global : {report.score_global:.1f}/100**  ",
        f"Seryvon {report.tool_version} · {generated} · schéma v{report.schema_version}",
        "",
        "## Scores par pilier",
        "",
        *_pillar_table(report),
        "",
        *_readiness_block(report),
        *_issues_block(report),
        *_criteria_block(report),
    ]
    return "\n".join(lines).rstrip() + "\n"
