# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests du rendu Markdown : contenu, échappement, déterminisme."""

from __future__ import annotations

from datetime import UTC, datetime

from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import ReadinessLevel, Severity, Status
from seryvon.models.report import AsoReadiness, AuditReport, Issue, PillarScore
from seryvon.reporting.markdown_report import report_to_markdown


def _report() -> AuditReport:
    return AuditReport(
        domain="example.com",
        tool_version="0.1.0.dev0",
        schema_version=6,
        started_at=datetime(2026, 6, 18, 9, 0, tzinfo=UTC),
        finished_at=datetime(2026, 6, 18, 9, 1, tzinfo=UTC),
        score_global=64.8,
        pillars={
            "seo": PillarScore(pillar="seo", score=72.1, measured=20, excluded=6),
            "geo": PillarScore(pillar="geo", score=0.0, measured=0, excluded=0),
        },
        criteria=[
            CriterionResult(
                key="meta.title",
                pillars=["seo"],
                score=100.0,
                status=Status.OK,
                explanation="Balise title conforme.",
            )
        ],
        issues=[
            Issue(
                criterion_key="meta.description",
                severity=Severity.CRITICAL,
                impact=2,
                effort=1,
                priority_score=4.0,
                priority_bucket="P1",
                recommendation="Rédiger une meta description de 120–158 caractères.",
            )
        ],
        aso_readiness=AsoReadiness(readiness_level=ReadinessLevel.BASIC, has_action_schema=True),
    )


def test_markdown_contains_sections() -> None:
    md = report_to_markdown(_report())
    assert "# Audit Seryvon — example.com" in md
    assert "64.8/100" in md
    assert "Scores par pilier" in md
    assert "| SEO |" in md
    assert "Readiness agentique" in md
    assert "`basic`" in md
    assert "Plan d'action (1 problèmes)" in md
    assert "meta.description" in md
    assert "### SEO" in md


def test_markdown_escapes_pipes() -> None:
    report = _report()
    report.issues[0].recommendation = "Faire A | B"
    md = report_to_markdown(report)
    assert "Faire A \\| B" in md
    assert "Faire A | B" not in md


def test_markdown_is_deterministic() -> None:
    report = _report()
    assert report_to_markdown(report) == report_to_markdown(report)
