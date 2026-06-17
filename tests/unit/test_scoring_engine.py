# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests du moteur de scoring : agrégation, renormalisation, garde-fous."""

from __future__ import annotations

from seryvon.core.config import DEFAULT_PILLAR_WEIGHTS, AuditConfig
from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import Status
from seryvon.models.report import PillarScore
from seryvon.models.signals import ExternalSignals, PageSignals, SignalBundle, SiteSignals
from seryvon.scoring.engine import run_criteria, score_global, score_pillar

PILLARS = ("seo", "geo", "gso", "aeo", "aso")


def _rich_bundle() -> SignalBundle:
    """Bundle multi-pages représentatif, avec signaux internes + externes."""
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


def test_score_global_excludes_unmeasured_pillars() -> None:
    """Les piliers sans critère mesuré (measured == 0) sont exclus et renormalisés."""
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
    """Déterminisme rejoué : un même SignalBundle reproduit exactement les scores."""
    bundle = _rich_bundle()
    cfg = AuditConfig.default()

    first = run_criteria(bundle, cfg)
    second = run_criteria(bundle, cfg)
    assert [r.model_dump() for r in first] == [r.model_dump() for r in second]

    pillars_a = {p: score_pillar(p, first) for p in PILLARS}
    pillars_b = {p: score_pillar(p, second) for p in PILLARS}
    assert {p: s.score for p, s in pillars_a.items()} == {p: s.score for p, s in pillars_b.items()}
    assert score_global(pillars_a, cfg) == score_global(pillars_b, cfg)


def test_run_criteria_applies_threshold_override() -> None:
    """La section thresholds: du YAML est transmise aux règles par le moteur."""
    bundle = SignalBundle(
        domain="ex.com",
        pages=[PageSignals(url="https://ex.com/", status_code=200, word_count=800)],
    )
    cfg = AuditConfig.default()
    cfg.thresholds = {"content.depth": {"target_words": 1600}}
    depth = next(r for r in run_criteria(bundle, cfg) if r.key == "content.depth")
    assert depth.score == 50.0  # 800 / 1600
    assert depth.threshold == {"min_words": 1600}
