# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the GEO on-page core (noise_ratio, entity_density, sources, authors,
cross-platform, freshness)."""

from __future__ import annotations

from datetime import UTC, datetime

from seryvon.models.enums import Status
from seryvon.models.signals import CitationMetrics, ExternalSignals, PageSignals, SignalBundle
from seryvon.scoring.rules.geo import (
    GeoAuthorsCriterion,
    GeoCitationConfidenceCriterion,
    GeoCitationPositionCriterion,
    GeoCitationRateCriterion,
    GeoCrossPlatformCriterion,
    GeoEntityDensityCriterion,
    GeoFreshnessCriterion,
    GeoKnowledgePresenceCriterion,
    GeoMentionRateCriterion,
    GeoNoiseRatioCriterion,
    GeoPrimarySourcesCriterion,
    GeoShareOfVoiceCriterion,
    _position_score,
)


def _page(url: str = "https://ex.com/", **kwargs: object) -> PageSignals:
    return PageSignals(url=url, **kwargs)  # type: ignore[arg-type]


def _bundle(*pages: PageSignals, audited_at: datetime | None = None) -> SignalBundle:
    return SignalBundle(domain="ex.com", pages=list(pages), audited_at=audited_at)


def test_noise_ratio() -> None:
    assert GeoNoiseRatioCriterion().evaluate(_bundle(_page(main_text_ratio=0.5))).score == 100
    assert GeoNoiseRatioCriterion().evaluate(_bundle(_page(main_text_ratio=0.1))).score == 50
    assert GeoNoiseRatioCriterion().evaluate(_bundle(_page())).status is Status.NOT_MEASURED


def test_entity_density() -> None:
    # 50 entities over 500 words = 0.10 -> within the target range -> 100.
    good = _page(entity_count=50, word_count=500)
    assert GeoEntityDensityCriterion().evaluate(_bundle(good)).score == 100
    # 2 entities over 500 words = 0.004 -> below the range -> proportional (20).
    sparse = _page(entity_count=2, word_count=500)
    assert GeoEntityDensityCriterion().evaluate(_bundle(sparse)).score == 20
    # 200 entities over 500 words = 0.40 -> too dense -> 60.
    dense = _page(entity_count=200, word_count=500)
    assert GeoEntityDensityCriterion().evaluate(_bundle(dense)).score == 60
    assert GeoEntityDensityCriterion().evaluate(_bundle(_page())).status is Status.NOT_MEASURED


def test_primary_sources_ratio() -> None:
    bundle = _bundle(
        _page("https://ex.com/a", external_link_domains=["doi.org"]),
        _page("https://ex.com/b"),
    )
    result = GeoPrimarySourcesCriterion().evaluate(bundle)
    assert result.score == 50.0
    assert result.pillars == ["geo", "aeo"]


def test_authors_presence() -> None:
    result = GeoAuthorsCriterion().evaluate(_bundle(_page(has_author=True)))
    assert result.score == 100
    assert result.pillars == ["geo", "aeo"]
    assert GeoAuthorsCriterion().evaluate(_bundle(_page())).score == 0


def test_cross_platform_target() -> None:
    four = _page(social_platforms=["twitter", "linkedin", "github", "youtube"])
    result = GeoCrossPlatformCriterion().evaluate(_bundle(four))
    assert result.score == 100
    assert result.pillars == ["geo", "aso"]
    two = _page(social_platforms=["twitter", "linkedin"])
    assert GeoCrossPlatformCriterion().evaluate(_bundle(two)).score == 50  # 2/4


def test_freshness_age_vs_reference() -> None:
    ref = datetime(2026, 6, 1, tzinfo=UTC)
    fresh = _bundle(_page(content_date="2026-05-15"), audited_at=ref)  # ~17 j
    assert GeoFreshnessCriterion().evaluate(fresh).score == 100
    stale = _bundle(_page(content_date="2025-06-01"), audited_at=ref)  # ~365 j
    assert GeoFreshnessCriterion().evaluate(stale).score == 0
    medium = _bundle(_page(content_date="2026-01-01"), audited_at=ref)  # ~151 j
    assert GeoFreshnessCriterion().evaluate(medium).score == 50


def test_freshness_not_measured_without_reference_or_date() -> None:
    no_ref = _bundle(_page(content_date="2026-05-15"))
    assert GeoFreshnessCriterion().evaluate(no_ref).status is Status.NOT_MEASURED
    no_date = _bundle(_page(), audited_at=datetime(2026, 6, 1, tzinfo=UTC))
    assert GeoFreshnessCriterion().evaluate(no_date).status is Status.NOT_MEASURED
    bad_date = _bundle(
        _page(content_date="pas-une-date"), audited_at=datetime(2026, 6, 1, tzinfo=UTC)
    )
    assert GeoFreshnessCriterion().evaluate(bad_date).status is Status.NOT_MEASURED


def _with_metrics(**kwargs: object) -> SignalBundle:
    return SignalBundle(
        domain="ex.com",
        external=ExternalSignals(citation_metrics=CitationMetrics(**kwargs)),  # type: ignore[arg-type]
    )


def test_citation_rate_not_measured_without_keys() -> None:
    assert GeoCitationRateCriterion().evaluate(_bundle(_page())).status is Status.NOT_MEASURED


def test_citation_rate_scored_from_metrics() -> None:
    bundle = _with_metrics(
        citation_rate=0.42, engines=["perplexity"], prompt_count=10, repetitions=5
    )
    result = GeoCitationRateCriterion().evaluate(bundle)
    assert result.score == 42.0
    assert result.pillars == ["geo"]
    assert result.weight == 2.0


def test_mention_rate_scored_from_metrics() -> None:
    bundle = _with_metrics(mention_rate=0.6)
    result = GeoMentionRateCriterion().evaluate(bundle)
    assert result.score == 60.0
    assert result.weight == 1.0
    assert GeoMentionRateCriterion().evaluate(_bundle(_page())).status is Status.NOT_MEASURED


def test_citation_confidence_scored_from_metrics() -> None:
    bundle = _with_metrics(citation_confidence=0.8, repetitions=5)
    result = GeoCitationConfidenceCriterion().evaluate(bundle)
    assert result.score == 80.0
    assert result.weight == 0.8
    assert GeoCitationConfidenceCriterion().evaluate(_bundle(_page())).status is Status.NOT_MEASURED


def test_knowledge_presence_scored() -> None:
    bundle = _with_metrics(knowledge_presence=0.7)
    result = GeoKnowledgePresenceCriterion().evaluate(bundle)
    assert result.score == 70.0
    assert result.weight == 0.8
    assert result.pillars == ["geo"]


def test_knowledge_presence_not_measured_when_none() -> None:
    assert GeoKnowledgePresenceCriterion().evaluate(_bundle(_page())).status is Status.NOT_MEASURED
    bundle = _with_metrics()  # knowledge_presence defaults to None
    assert GeoKnowledgePresenceCriterion().evaluate(bundle).status is Status.NOT_MEASURED


def test_share_of_voice_scored() -> None:
    bundle = _with_metrics(share_of_voice=0.55)
    result = GeoShareOfVoiceCriterion().evaluate(bundle)
    assert result.score == 55.0
    assert result.weight == 1.0


def test_share_of_voice_not_measured_without_competitors() -> None:
    assert GeoShareOfVoiceCriterion().evaluate(_bundle(_page())).status is Status.NOT_MEASURED
    bundle = _with_metrics()  # share_of_voice defaults to None
    assert GeoShareOfVoiceCriterion().evaluate(bundle).status is Status.NOT_MEASURED


def test_citation_position_score_formula() -> None:
    assert _position_score(1.0) == 100.0
    assert _position_score(2.0) == 80.0
    assert _position_score(3.0) == 60.0
    assert _position_score(6.0) == 0.0
    assert _position_score(7.0) == 0.0  # clamped at 0


def test_citation_position_criterion_scored() -> None:
    bundle = _with_metrics(average_position=2.0)
    result = GeoCitationPositionCriterion().evaluate(bundle)
    assert result.score == 80.0
    assert result.weight == 0.8
    assert result.pillars == ["geo"]


def test_citation_position_not_measured_when_none() -> None:
    assert GeoCitationPositionCriterion().evaluate(_bundle(_page())).status is Status.NOT_MEASURED
    bundle = _with_metrics()  # average_position defaults to None
    assert GeoCitationPositionCriterion().evaluate(bundle).status is Status.NOT_MEASURED
