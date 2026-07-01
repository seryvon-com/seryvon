# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the scoring engine: aggregation, renormalization, safeguards."""

from __future__ import annotations

from seryvon.core.audit import _build_measurement_profile, _rule_catalog_digest
from seryvon.core.config import DEFAULT_PILLAR_WEIGHTS, AuditConfig
from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import CoverageLabel, Status
from seryvon.models.report import PillarScore
from seryvon.models.signals import ExternalSignals, PageSignals, SignalBundle, SiteSignals
from seryvon.scoring.engine import (
    coverage_label,
    run_criteria,
    score_coverage,
    score_global,
    score_pillar,
)

PILLARS = ("seo", "geo", "gso", "aeo", "aso")


def test_coverage_excludes_not_applicable_from_base() -> None:
    results = [
        CriterionResult(key="a", pillars=["seo"], score=100.0, status=Status.OK, weight=2.0),
        CriterionResult(
            key="b", pillars=["seo"], score=0.0, status=Status.NOT_MEASURED, weight=2.0
        ),
        CriterionResult(
            key="c", pillars=["seo"], score=0.0, status=Status.NOT_APPLICABLE, weight=1.0
        ),
    ]
    ps = score_pillar("seo", results)
    # eligible = a + b (weight 4); measured = a (weight 2) -> coverage 0.5; c is not counted.
    assert ps.coverage == 0.5
    assert ps.measured == 1
    assert ps.not_applicable == 1
    assert ps.score == 50.0  # raw=100 * coverage=0.5 (coverage penalty applied)
    assert score_coverage(results) == 0.5


def _rich_bundle() -> SignalBundle:
    """Representative multi-page bundle, with internal + external signals."""
    return SignalBundle(
        domain="ex.com",
        pages=[
            PageSignals(
                url="https://ex.com/",
                status_code=200,
                title="Accueil — un titre de longueur tout à fait correcte ici",
                meta_description="d" * 130,
                canonical="https://ex.com/",
                h1_count=1,
                headings={"h1": 1, "h2": 3},
                word_count=900,
                text_ratio=0.21,
                internal_links=5,
                internal_link_targets=["https://ex.com/a"],
                images_total=3,
                images_with_alt=2,
                structured_data_types=["Organization"],
                open_graph={"og:title": "T", "og:type": "website"},
            ),
            PageSignals(
                url="https://ex.com/a",
                status_code=200,
                title="Page A — un autre titre de longueur correcte ici aussi",
                word_count=400,
                internal_links=2,
                redirects=1,
            ),
        ],
        site=SiteSignals(robots_found=True, sitemap_valid=True, sitemap_url_count=2),
        external=ExternalSignals(
            core_web_vitals={"lcp": 2000.0, "cls": 0.05, "inp": 150.0},
            lighthouse_performance=0.9,
            open_page_rank=5.0,
        ),
    )


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
    # raw=100, coverage=2/7≈0.2857 -> score=100*0.2857≈28.57 (coverage penalty applied)
    assert ps.score == 28.57
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


def test_score_global_excludes_unmeasured_pillars() -> None:
    """Pillars with no measured criterion (measured == 0) are excluded and renormalized."""
    cfg = AuditConfig.default()
    pillars = {
        "seo": PillarScore(pillar="seo", score=80.0, measured=5, excluded=0),
        "geo": PillarScore(pillar="geo", score=0.0, measured=0, excluded=3),  # exclu
        "gso": PillarScore(pillar="gso", score=60.0, measured=2, excluded=1),
        "aeo": PillarScore(pillar="aeo", score=0.0, measured=0, excluded=2),  # exclu
        "aso": PillarScore(pillar="aso", score=40.0, measured=1, excluded=0),
    }
    overall = score_global(pillars, cfg)
    w = DEFAULT_PILLAR_WEIGHTS
    expected = round(
        (80.0 * w["seo"] + 60.0 * w["gso"] + 40.0 * w["aso"]) / (w["seo"] + w["gso"] + w["aso"]),
        2,
    )
    assert overall == expected


def test_score_clamped_to_range(bundle_with_title: SignalBundle) -> None:
    results = run_criteria(bundle_with_title, AuditConfig.default())
    for r in results:
        assert 0.0 <= r.score <= 100.0


def test_scoring_is_deterministic_on_rich_bundle() -> None:
    """Determinism replayed: the same SignalBundle reproduces the scores exactly."""
    bundle = _rich_bundle()
    cfg = AuditConfig.default()

    first = run_criteria(bundle, cfg)
    second = run_criteria(bundle, cfg)
    assert [r.model_dump() for r in first] == [r.model_dump() for r in second]

    pillars_a = {p: score_pillar(p, first) for p in PILLARS}
    pillars_b = {p: score_pillar(p, second) for p in PILLARS}
    assert {p: s.score for p, s in pillars_a.items()} == {p: s.score for p, s in pillars_b.items()}
    assert score_global(pillars_a, cfg) == score_global(pillars_b, cfg)


def test_coverage_label_thresholds() -> None:
    """SIC doc 04 §4 boundaries."""
    assert coverage_label(1.00) == CoverageLabel.COMPLETE
    assert coverage_label(0.90) == CoverageLabel.COMPLETE
    assert coverage_label(0.89) == CoverageLabel.SUBSTANTIAL
    assert coverage_label(0.70) == CoverageLabel.SUBSTANTIAL
    assert coverage_label(0.69) == CoverageLabel.PARTIAL
    assert coverage_label(0.40) == CoverageLabel.PARTIAL
    assert coverage_label(0.39) == CoverageLabel.INSUFFICIENT
    assert coverage_label(0.00) == CoverageLabel.INSUFFICIENT


def test_pillar_score_carries_coverage_label() -> None:
    results = [
        CriterionResult(key="a", pillars=["seo"], score=100.0, status=Status.OK, weight=1.0),
    ]
    ps = score_pillar("seo", results)
    assert ps.coverage == 1.0
    assert ps.coverage_label == CoverageLabel.COMPLETE


def test_pillar_score_insufficient_when_all_not_measured() -> None:
    results = [
        CriterionResult(key="a", pillars=["geo"], score=0.0, status=Status.NOT_MEASURED, weight=1.0)
    ]
    ps = score_pillar("geo", results)
    assert ps.coverage == 0.0
    assert ps.coverage_label == CoverageLabel.INSUFFICIENT


def test_measurement_profile_digest_is_deterministic() -> None:
    config = AuditConfig.default()
    p1 = _build_measurement_profile(config, ["crawler"])
    p2 = _build_measurement_profile(config, ["crawler"])
    assert p1.digest == p2.digest


def test_measurement_profile_digest_changes_with_connectors() -> None:
    config = AuditConfig.default()
    p1 = _build_measurement_profile(config, ["crawler"])
    p2 = _build_measurement_profile(config, ["crawler", "pagespeed"])
    assert p1.digest != p2.digest


def test_measurement_profile_digest_changes_with_config() -> None:
    config_a = AuditConfig.default()
    config_b = AuditConfig.default()
    config_b.pillar_weights["seo"] = 0.99
    p1 = _build_measurement_profile(config_a, ["crawler"])
    p2 = _build_measurement_profile(config_b, ["crawler"])
    assert p1.digest != p2.digest


def test_rule_catalog_digest_is_stable() -> None:
    d1 = _rule_catalog_digest()
    d2 = _rule_catalog_digest()
    assert d1 == d2
    assert len(d1) == 16


def test_run_criteria_applies_threshold_override() -> None:
    """The YAML thresholds: section is passed to the rules by the engine."""
    bundle = SignalBundle(
        domain="ex.com",
        pages=[PageSignals(url="https://ex.com/", status_code=200, word_count=800)],
    )
    cfg = AuditConfig.default()
    cfg.thresholds = {"content.depth": {"target_words": 1600}}
    depth = next(r for r in run_criteria(bundle, cfg) if r.key == "content.depth")
    assert depth.score == 50.0  # 800 / 1600
    assert depth.threshold == {"min_words": 1600}
