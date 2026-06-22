# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for scorecard comparison (M6, SIC docs 04 §7 + 06 §5)."""

from __future__ import annotations

import pytest

from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import Status
from seryvon.models.report import AuditReport, MeasurementProfile, PillarScore
from seryvon.scoring import classify, compare_scorecards
from seryvon.scoring.comparison import Comparability, ComparisonMode, IncomparableError


def _profile(digest: str = "d0", **overrides: object) -> MeasurementProfile:
    fields: dict[str, object] = {
        "seryvon_version": "0.1.0",
        "signal_schema_version": 8,
        "rule_catalog_digest": "rc0",
        "pillar_weights": {"seo": 0.3, "geo": 0.22, "gso": 0.18, "aeo": 0.15, "aso": 0.15},
        "thresholds": {},
        "criteria_overrides": {},
        "active_connectors": ["crawler"],
    }
    fields.update(overrides)
    return MeasurementProfile(**fields, digest=digest)  # type: ignore[arg-type]


def _crit(
    key: str, score: float, status: Status = Status.OK, weight: float = 1.0
) -> CriterionResult:
    return CriterionResult(key=key, pillars=["seo"], score=score, status=status, weight=weight)


def _report(
    profile: MeasurementProfile, criteria: list[CriterionResult], glob: float
) -> AuditReport:
    pillars = {"seo": PillarScore(pillar="seo", score=glob, measured=len(criteria))}
    return AuditReport(
        domain="example.com",
        tool_version="0.1.0",
        schema_version=8,
        started_at="2026-06-21T00:00:00Z",  # type: ignore[arg-type]
        score_global=glob,
        pillars=pillars,
        criteria=criteria,
        measurement_profile=profile,
    )


# --------------------------------------------------------------------------- #
# classify                                                                    #
# --------------------------------------------------------------------------- #
def test_classify_exact_on_identical_digest() -> None:
    comp, diffs = classify(_profile("same"), _profile("same"))
    assert comp is Comparability.EXACT
    assert diffs == []


def test_classify_compatible_on_version_only() -> None:
    comp, diffs = classify(_profile("a"), _profile("b", seryvon_version="0.2.0"))
    assert comp is Comparability.COMPATIBLE
    assert diffs == ["seryvon_version"]


def test_classify_intersection_on_connector_diff() -> None:
    comp, diffs = classify(_profile("a"), _profile("b", active_connectors=["crawler", "pagespeed"]))
    assert comp is Comparability.INTERSECTION
    assert "active_connectors" in diffs


def test_classify_incompatible_on_weight_change() -> None:
    comp, _ = classify(_profile("a"), _profile("b", pillar_weights={"seo": 1.0}))
    assert comp is Comparability.INCOMPATIBLE


def test_classify_incompatible_on_rule_catalog_change() -> None:
    comp, _ = classify(_profile("a"), _profile("b", rule_catalog_digest="rc1"))
    assert comp is Comparability.INCOMPATIBLE


# --------------------------------------------------------------------------- #
# compare_scorecards                                                          #
# --------------------------------------------------------------------------- #
def test_strict_exact_computes_global_delta() -> None:
    left = _report(_profile("same"), [_crit("meta.title", 60.0)], glob=60.0)
    right = _report(_profile("same"), [_crit("meta.title", 80.0)], glob=80.0)
    result = compare_scorecards(left, right, ComparisonMode.STRICT)
    assert result.comparability is Comparability.EXACT
    assert result.global_delta == 20.0
    assert not result.recomputed
    title = next(c for c in result.criteria if c.key == "meta.title")
    assert title.delta == 20.0


def test_strict_over_incompatible_raises() -> None:
    left = _report(_profile("a"), [_crit("meta.title", 60.0)], glob=60.0)
    right = _report(_profile("b", pillar_weights={"seo": 1.0}), [_crit("meta.title", 80.0)], 80.0)
    with pytest.raises(IncomparableError) as exc:
        compare_scorecards(left, right, ComparisonMode.STRICT)
    assert exc.value.comparability is Comparability.INCOMPATIBLE
    assert ComparisonMode.DESCRIPTIVE in exc.value.allowed_modes
    assert ComparisonMode.STRICT not in exc.value.allowed_modes


def test_intersection_recomputes_on_common_criteria() -> None:
    # left measured {a, b}; right measured {a} (b not_measured) -> common = {a}.
    left = _report(
        _profile("a"),
        [_crit("crit.a", 40.0), _crit("crit.b", 100.0)],
        glob=70.0,
    )
    right = _report(
        _profile("b", active_connectors=["crawler", "pagespeed"]),
        [_crit("crit.a", 80.0), _crit("crit.b", 0.0, status=Status.NOT_MEASURED)],
        glob=80.0,
    )
    result = compare_scorecards(left, right, ComparisonMode.INTERSECTION)
    assert result.recomputed
    assert result.common_criteria == ["crit.a"]
    # Recomputed over crit.a only: left 40, right 80 -> delta 40.
    assert result.left_global == 40.0
    assert result.right_global == 80.0
    assert result.global_delta == 40.0


def test_descriptive_over_incompatible_no_delta() -> None:
    left = _report(_profile("a"), [_crit("meta.title", 60.0)], glob=60.0)
    right = _report(_profile("b", pillar_weights={"seo": 1.0}), [_crit("meta.title", 80.0)], 80.0)
    result = compare_scorecards(left, right, ComparisonMode.DESCRIPTIVE)
    assert result.comparability is Comparability.INCOMPATIBLE
    assert result.global_delta is None
    seo = next(p for p in result.pillars if p.pillar == "seo")
    assert seo.left_score == 60.0
    assert seo.right_score == 80.0
    assert seo.delta is None


def test_missing_profile_is_incomparable() -> None:
    left = _report(_profile("a"), [_crit("meta.title", 60.0)], glob=60.0)
    right = left.model_copy(update={"measurement_profile": None})
    with pytest.raises(IncomparableError):
        compare_scorecards(left, right, ComparisonMode.STRICT)
