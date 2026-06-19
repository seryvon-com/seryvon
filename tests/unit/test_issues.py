# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the prioritized action plan (issues)."""

from __future__ import annotations

from typing import Any

from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import Severity, Status
from seryvon.scoring.issues import build_issues


def _result(
    key: str,
    status: Status,
    *,
    weight: float = 1.0,
    pillars: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
) -> CriterionResult:
    return CriterionResult(
        key=key,
        pillars=pillars or ["seo"],
        score=0.0,
        status=status,
        weight=weight,
        evidence=evidence or {},
    )


def test_only_warning_and_critical_generate_issues() -> None:
    results = [
        _result("struct.schema", Status.OK),
        _result("authority.opr", Status.NOT_MEASURED),
        _result("meta.title", Status.CRITICAL, weight=1.5),
        _result("content.text_ratio", Status.WARNING, weight=0.6),
    ]
    issues = build_issues(results)
    assert [i.criterion_key for i in issues] == ["meta.title", "content.text_ratio"]


def test_priority_formula_and_bucket() -> None:
    # meta.title critical: impact 2 (1.5×1), severity 2, effort 1 -> 4.0 -> P1.
    issue = build_issues([_result("meta.title", Status.CRITICAL, weight=1.5)])[0]
    assert issue.severity is Severity.CRITICAL
    assert issue.impact == 2
    assert issue.effort == 1
    assert issue.priority_score == 4.0
    assert issue.priority_bucket == "P1"


def test_multipillar_impact_is_higher() -> None:
    # struct.schema warning : poids 1.5 × 4 piliers = 6 -> impact 3.
    issue = build_issues(
        [_result("struct.schema", Status.WARNING, weight=1.5, pillars=["seo", "gso", "aeo", "aso"])]
    )[0]
    assert issue.impact == 3


def test_issues_sorted_by_priority_desc() -> None:
    results = [
        _result("content.text_ratio", Status.WARNING, weight=0.6),  # 0.5 -> P4
        _result("meta.title", Status.CRITICAL, weight=1.5),  # 4.0 -> P1
    ]
    issues = build_issues(results)
    assert [i.priority_bucket for i in issues] == ["P1", "P4"]


def test_recommendation_and_affected_pages() -> None:
    result = _result(
        "meta.title", Status.CRITICAL, weight=1.5, evidence={"non_conformes": ["https://ex.com/a"]}
    )
    issue = build_issues([result])[0]
    assert "title" in issue.recommendation.lower()
    assert issue.affected_pages == ["https://ex.com/a"]


def test_unknown_key_uses_fallback_recommendation() -> None:
    issue = build_issues([_result("custom.key", Status.WARNING)])[0]
    assert issue.recommendation == "Corriger le critère custom.key."
