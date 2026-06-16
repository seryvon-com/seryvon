# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests du moteur de scoring : agrégation, renormalisation, garde-fous."""

from __future__ import annotations

from seryvon.core.config import AuditConfig
from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import Status
from seryvon.models.signals import SignalBundle
from seryvon.scoring.engine import run_criteria, score_global, score_pillar


def test_run_criteria_returns_results(bundle_with_title: SignalBundle) -> None:
    results = run_criteria(bundle_with_title, AuditConfig.default())
    keys = {r.key for r in results}
    assert "meta.title" in keys


def test_run_criteria_applies_weight_override(bundle_with_title: SignalBundle) -> None:
    config = AuditConfig.default()
    config.criteria_overrides = {"meta.title": {"weight": 5.0}}
    results = run_criteria(bundle_with_title, config)
    title = next(r for r in results if r.key == "meta.title")
    assert title.weight == 5.0


def test_run_criteria_is_deterministic(bundle_with_title: SignalBundle) -> None:
    cfg = AuditConfig.default()
    a = run_criteria(bundle_with_title, cfg)
    b = run_criteria(bundle_with_title, cfg)
    assert [r.model_dump() for r in a] == [r.model_dump() for r in b]


def _result(key: str, pillar: str, score: float, weight: float, status: Status) -> CriterionResult:
    return CriterionResult(key=key, pillars=[pillar], score=score, status=status, weight=weight)


def test_score_pillar_weighted_average() -> None:
    results = [
        _result("a", "seo", 100.0, 2.0, Status.OK),
        _result("b", "seo", 50.0, 1.0, Status.WARNING),
    ]
    ps = score_pillar("seo", results)
    # (100*2 + 50*1) / 3 = 83.33
    assert ps.score == 83.33
    assert ps.measured == 2
    assert ps.excluded == 0


def test_score_pillar_renormalises_not_measured() -> None:
    results = [
        _result("a", "seo", 100.0, 2.0, Status.OK),
        CriterionResult(
            key="b", pillars=["seo"], score=0.0, status=Status.NOT_MEASURED, weight=5.0
        ),
    ]
    ps = score_pillar("seo", results)
    # Le not_measured est exclu : seul 'a' compte -> 100
    assert ps.score == 100.0
    assert ps.measured == 1
    assert ps.excluded == 1


def test_score_pillar_all_not_measured() -> None:
    results = [
        CriterionResult(key="a", pillars=["geo"], score=0.0, status=Status.NOT_MEASURED, weight=1.0)
    ]
    ps = score_pillar("geo", results)
    assert ps.score == 0.0
    assert ps.measured == 0
    assert ps.excluded == 1


def test_score_global_excludes_unmeasured_pillars(bundle_with_title: SignalBundle) -> None:
    """Seul SEO est mesuré en Phase 0 -> le global égale le score SEO."""
    cfg = AuditConfig.default()
    results = run_criteria(bundle_with_title, cfg)
    pillars = {p: score_pillar(p, results) for p in ("seo", "geo", "gso", "aeo", "aso")}
    overall = score_global(pillars, cfg)
    assert overall == pillars["seo"].score


def test_score_clamped_to_range(bundle_with_title: SignalBundle) -> None:
    results = run_criteria(bundle_with_title, AuditConfig.default())
    for r in results:
        assert 0.0 <= r.score <= 100.0
