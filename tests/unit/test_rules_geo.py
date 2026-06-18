# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests du cœur GEO on-page (noise_ratio, entity_density, sources, auteurs,
cross-platform, freshness)."""

from __future__ import annotations

from datetime import UTC, datetime

from seryvon.models.enums import Status
from seryvon.models.signals import PageSignals, SignalBundle
from seryvon.scoring.rules.geo import (
    GeoAuthorsCriterion,
    GeoCrossPlatformCriterion,
    GeoEntityDensityCriterion,
    GeoFreshnessCriterion,
    GeoNoiseRatioCriterion,
    GeoPrimarySourcesCriterion,
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
    # 50 entités sur 500 mots = 0.10 -> dans la plage cible -> 100.
    good = _page(entity_count=50, word_count=500)
    assert GeoEntityDensityCriterion().evaluate(_bundle(good)).score == 100
    # 2 entités sur 500 mots = 0.004 -> sous la plage -> proportionnel (20).
    sparse = _page(entity_count=2, word_count=500)
    assert GeoEntityDensityCriterion().evaluate(_bundle(sparse)).score == 20
    # 200 entités sur 500 mots = 0.40 -> trop dense -> 60.
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
