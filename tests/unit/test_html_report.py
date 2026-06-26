# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""HTML rendering tests: content, escaping (XSS), determinism."""

from __future__ import annotations

from datetime import UTC, datetime

from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import Status
from seryvon.models.report import AuditReport, PillarScore
from seryvon.reporting.html_report import report_to_html


def _report(criteria: list[CriterionResult] | None = None) -> AuditReport:
    if criteria is None:
        criteria = [
            CriterionResult(
                key="meta.title",
                pillars=["seo"],
                score=100.0,
                status=Status.OK,
                explanation="Balise title : 1/1 page(s) conforme(s).",
                weight=1.5,
            )
        ]
    return AuditReport(
        domain="example.com",
        tool_version="0.1.0.dev0",
        schema_version=3,
        started_at=datetime(2026, 6, 17, 12, 0, tzinfo=UTC),
        finished_at=datetime(2026, 6, 17, 12, 1, tzinfo=UTC),
        score_global=72.5,
        pillars={
            "seo": PillarScore(pillar="seo", score=72.5, measured=20, excluded=2),
            "geo": PillarScore(pillar="geo", score=0.0, measured=0, excluded=0),
        },
        criteria=criteria,
    )


def test_html_contains_core_data() -> None:
    html = report_to_html(_report())
    assert "<!DOCTYPE html>" in html
    assert "example.com" in html
    assert "72.5" in html
    assert "SEO" in html
    assert "meta.title" in html
    assert "Balise title" in html


def test_html_unmeasured_pillar_shows_dash() -> None:
    html = report_to_html(_report())
    assert "GEO" in html
    assert "—" in html  # unmeasured pillar


def test_html_escapes_untrusted_content() -> None:
    malicious = CriterionResult(
        key="meta.title",
        pillars=["seo"],
        score=0.0,
        status=Status.CRITICAL,
        explanation="<script>alert('xss')</script>",
        raw_value={"title": "<img src=x onerror=alert(1)>"},
        weight=1.5,
    )
    html = report_to_html(_report([malicious]))
    # No active tag must remain: everything is escaped.
    assert "<script>alert" not in html
    assert "<img src=x onerror" not in html
    assert "&lt;script&gt;" in html


def test_html_is_deterministic() -> None:
    report = _report()
    assert report_to_html(report) == report_to_html(report)


def test_html_warning_band_for_mid_score() -> None:
    """A global score in [50, 80) lands in the warning band — covers the middle CSS branch."""
    report = _report()
    report.score_global = 65.0
    html = report_to_html(report)
    assert 'class="global score-warning"' in html


def test_html_ok_band_for_high_score() -> None:
    """A global score >= 80 lands in the ok band — covers the OK CSS branch."""
    report = _report()
    report.score_global = 92.0
    html = report_to_html(report)
    assert 'class="global score-ok"' in html
