# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the SEO rule `meta.title` — all threshold tiers."""

from __future__ import annotations

from seryvon.models.enums import Status
from seryvon.models.signals import PageSignals, SignalBundle, SiteSignals
from seryvon.scoring.rules.seo import (
    ContentDepthCriterion,
    ContentTextRatioCriterion,
    CrawlHttpsCriterion,
    CrawlIndexableCriterion,
    CrawlRedirectsCriterion,
    CrawlSitemapCriterion,
    HreflangCriterion,
    ImgAltCriterion,
    LinksInternalCriterion,
    LinksOrphansCriterion,
    MetaCanonicalCriterion,
    MetaDescriptionCriterion,
    MetaRobotsCriterion,
    MetaTitleCriterion,
    MetaTitleUniqueCriterion,
    OpenGraphCriterion,
    StructH1Criterion,
    StructHierarchyCriterion,
    StructSchemaCriterion,
    TwitterCardCriterion,
)


def _bundle(title: str | None) -> SignalBundle:
    return SignalBundle(domain="ex.com", pages=[PageSignals(url="https://ex.com/", title=title)])


def _page(url: str = "https://ex.com/", **kwargs: object) -> PageSignals:
    return PageSignals(url=url, **kwargs)  # type: ignore[arg-type]


def _pages(*pages: PageSignals) -> SignalBundle:
    return SignalBundle(domain="ex.com", pages=list(pages))


def test_title_optimal_scores_100() -> None:
    result = MetaTitleCriterion().evaluate(_bundle("Un titre de longueur tout à fait correcte"))
    assert result.score == 100.0
    assert result.status is Status.OK


def test_title_absent_scores_0() -> None:
    result = MetaTitleCriterion().evaluate(_bundle(None))
    assert result.score == 0.0
    assert result.status is Status.CRITICAL


def test_title_too_short() -> None:
    result = MetaTitleCriterion().evaluate(_bundle("Trop court"))
    assert result.score == 60.0
    assert result.status is Status.WARNING


def test_title_too_long() -> None:
    long_title = (
        "Un titre vraiment beaucoup trop long qui dépasse la limite recommandée de soixante"
    )
    result = MetaTitleCriterion().evaluate(_bundle(long_title))
    assert result.score == 70.0
    assert result.status is Status.WARNING


def test_title_result_is_traceable() -> None:
    result = MetaTitleCriterion().evaluate(_bundle("Un titre de longueur tout à fait correcte"))
    assert result.threshold == {"min": 30, "max": 60}
    assert result.evidence.get("source")
    assert result.pillars == ["seo"]


def test_no_page_yields_zero() -> None:
    empty = SignalBundle(domain="ex.com", pages=[])
    result = MetaTitleCriterion().evaluate(empty)
    assert result.score == 0.0


def test_title_aggregates_across_pages() -> None:
    bundle = _pages(
        _page("https://ex.com/a", title="Un titre tout à fait correct pour la page A"),  # 100
        _page("https://ex.com/b", title=None),  # 0
    )
    result = MetaTitleCriterion().evaluate(bundle)
    assert result.score == 50.0  # moyenne (100 + 0) / 2
    assert result.raw_value == {"pages": 2, "passing": 1, "mean_score": 50.0}
    assert result.evidence["non_conformes"] == ["https://ex.com/b"]


def test_page_criterion_not_measured_without_pages() -> None:
    result = MetaDescriptionCriterion().evaluate(SignalBundle(domain="ex.com", pages=[]))
    assert result.status is Status.NOT_MEASURED


# --------------------------------------------------------------------------- #
# Metadata                                                                     #
# --------------------------------------------------------------------------- #
def test_description_paliers() -> None:
    optimal = "x" * 130
    assert MetaDescriptionCriterion().evaluate(_pages(_page(meta_description=optimal))).score == 100
    assert MetaDescriptionCriterion().evaluate(_pages(_page(meta_description="court"))).score == 60
    assert MetaDescriptionCriterion().evaluate(_pages(_page())).score == 0


def test_canonical_paliers() -> None:
    absolute = _page(canonical="https://ex.com/page")
    relative = _page(canonical="/page")
    assert MetaCanonicalCriterion().evaluate(_pages(absolute)).score == 100
    assert MetaCanonicalCriterion().evaluate(_pages(relative)).score == 70
    assert MetaCanonicalCriterion().evaluate(_pages(_page())).score == 0


def test_robots_indexable() -> None:
    assert MetaRobotsCriterion().evaluate(_pages(_page())).score == 100
    assert MetaRobotsCriterion().evaluate(_pages(_page(meta_robots="index,follow"))).score == 100
    noindex = _page(meta_robots="noindex, follow")
    assert MetaRobotsCriterion().evaluate(_pages(noindex)).score == 0


def test_title_unique() -> None:
    distinct = _pages(_page(title="Titre A"), _page(title="Titre B"))
    assert MetaTitleUniqueCriterion().evaluate(distinct).score == 100
    dup = _pages(_page(title="Même titre"), _page(title="Même titre"))
    assert MetaTitleUniqueCriterion().evaluate(dup).score == 50
    none = _pages(_page(), _page())
    assert MetaTitleUniqueCriterion().evaluate(none).status is Status.NOT_MEASURED


# --------------------------------------------------------------------------- #
# Social metadata                                                              #
# --------------------------------------------------------------------------- #
def test_open_graph_completeness() -> None:
    full = _page(
        open_graph={
            "og:title": "T",
            "og:description": "D",
            "og:image": "I",
            "og:url": "U",
            "og:type": "website",
        }
    )
    assert OpenGraphCriterion().evaluate(_pages(full)).score == 100
    partial = _page(open_graph={"og:title": "T", "og:description": "D"})
    assert OpenGraphCriterion().evaluate(_pages(partial)).score == 40  # 2/5
    assert OpenGraphCriterion().evaluate(_pages(_page())).score == 0


def test_twitter_cards() -> None:
    complete = _page(
        twitter_card={"twitter:card": "summary", "twitter:title": "T", "twitter:description": "D"}
    )
    assert TwitterCardCriterion().evaluate(_pages(complete)).score == 100
    partial = _page(twitter_card={"twitter:card": "summary"})
    assert TwitterCardCriterion().evaluate(_pages(partial)).score == 50
    assert TwitterCardCriterion().evaluate(_pages(_page())).score == 0


# --------------------------------------------------------------------------- #
# Structure                                                                    #
# --------------------------------------------------------------------------- #
def test_struct_h1() -> None:
    assert StructH1Criterion().evaluate(_pages(_page(h1_count=1))).score == 100
    assert StructH1Criterion().evaluate(_pages(_page(h1_count=0))).score == 0
    assert StructH1Criterion().evaluate(_pages(_page(h1_count=3))).score == 50


def test_struct_hierarchy() -> None:
    coherent = _page(h1_count=1, headings={"h1": 1, "h2": 2, "h3": 1})
    assert StructHierarchyCriterion().evaluate(_pages(coherent)).score == 100
    gap = _page(h1_count=1, headings={"h1": 1, "h3": 1})  # saut h1 -> h3
    assert StructHierarchyCriterion().evaluate(_pages(gap)).score == 50
    no_h1 = _page(h1_count=0, headings={"h2": 1})
    assert StructHierarchyCriterion().evaluate(_pages(no_h1)).score == 50
    assert StructHierarchyCriterion().evaluate(_pages(_page())).score == 0


def test_struct_schema() -> None:
    assert (
        StructSchemaCriterion().evaluate(_pages(_page(structured_data_types=["Org"]))).score == 100
    )
    assert StructSchemaCriterion().evaluate(_pages(_page())).score == 0


# --------------------------------------------------------------------------- #
# Contenu                                                                      #
# --------------------------------------------------------------------------- #
def test_content_depth() -> None:
    assert ContentDepthCriterion().evaluate(_pages(_page(word_count=800))).score == 100
    assert ContentDepthCriterion().evaluate(_pages(_page(word_count=400))).score == 50
    assert ContentDepthCriterion().evaluate(_pages(_page(word_count=1200))).score == 100


def test_content_depth_threshold_override() -> None:
    bundle = _pages(_page(word_count=800))
    assert ContentDepthCriterion().evaluate(bundle).score == 100.0  # default 800 words
    overridden = ContentDepthCriterion().evaluate(bundle, {"content.depth": {"target_words": 1600}})
    assert overridden.score == 50.0  # 800 / 1600
    assert overridden.threshold == {"min_words": 1600}


def test_content_text_ratio() -> None:
    assert ContentTextRatioCriterion().evaluate(_pages(_page(text_ratio=0.2))).score == 100
    assert ContentTextRatioCriterion().evaluate(_pages(_page(text_ratio=0.075))).score == 50
    assert ContentTextRatioCriterion().evaluate(_pages(_page(text_ratio=None))).score == 0


# --------------------------------------------------------------------------- #
# Maillage                                                                     #
# --------------------------------------------------------------------------- #
def test_links_internal() -> None:
    assert LinksInternalCriterion().evaluate(_pages(_page(internal_links=5))).score == 100
    assert LinksInternalCriterion().evaluate(_pages(_page(internal_links=0))).score == 0
    assert LinksInternalCriterion().evaluate(_pages(_page(internal_links=1))).score == 60


def test_links_orphans() -> None:
    home = _page("https://ex.com/", internal_link_targets=["https://ex.com/a"])
    linked = _page("https://ex.com/a")
    orphan = _page("https://ex.com/b")
    result = LinksOrphansCriterion().evaluate(_pages(home, linked, orphan))
    assert result.score == 50.0  # 1 orpheline sur 2 pages hors home
    assert result.evidence["orphelines"] == ["https://ex.com/b"]


def test_links_orphans_not_measured_single_page() -> None:
    result = LinksOrphansCriterion().evaluate(_pages(_page()))
    assert result.status is Status.NOT_MEASURED


# --------------------------------------------------------------------------- #
# Accessibility                                                                #
# --------------------------------------------------------------------------- #
def test_img_alt_ratio() -> None:
    bundle = _pages(
        _page("https://ex.com/a", images_total=2, images_with_alt=2),
        _page("https://ex.com/b", images_total=2, images_with_alt=1),
    )
    assert ImgAltCriterion().evaluate(bundle).score == 75.0  # 3/4


def test_img_alt_not_measured_without_images() -> None:
    result = ImgAltCriterion().evaluate(_pages(_page()))
    assert result.status is Status.NOT_MEASURED


# --------------------------------------------------------------------------- #
# Crawl                                                                        #
# --------------------------------------------------------------------------- #
def test_crawl_indexable() -> None:
    bundle = _pages(
        _page("https://ex.com/a", status_code=200),
        _page("https://ex.com/b", status_code=404),
        _page("https://ex.com/c", status_code=200, meta_robots="noindex"),
    )
    assert CrawlIndexableCriterion().evaluate(bundle).score == round(1 / 3 * 100, 2)


def test_crawl_sitemap() -> None:
    valid = SignalBundle(
        domain="ex.com", site=SiteSignals(sitemap_valid=True, sitemap_url_count=10)
    )
    assert CrawlSitemapCriterion().evaluate(valid).score == 100
    invalid = SignalBundle(domain="ex.com")
    assert CrawlSitemapCriterion().evaluate(invalid).score == 0


def test_crawl_https() -> None:
    bundle = _pages(_page("https://ex.com/a"), _page("http://ex.com/b"))
    assert CrawlHttpsCriterion().evaluate(bundle).score == 50.0


def test_crawl_redirects() -> None:
    assert CrawlRedirectsCriterion().evaluate(_pages(_page(redirects=0))).score == 100
    assert CrawlRedirectsCriterion().evaluate(_pages(_page(redirects=2))).score == 50
    assert CrawlRedirectsCriterion().evaluate(_pages(_page(redirects=5))).score == 0


# --------------------------------------------------------------------------- #
# i18n                                                                         #
# --------------------------------------------------------------------------- #
def test_hreflang() -> None:
    with_default = _page(hreflang={"fr": "/fr", "x-default": "/"})
    assert HreflangCriterion().evaluate(_pages(with_default)).score == 100
    without_default = _page(hreflang={"fr": "/fr", "en": "/en"})
    assert HreflangCriterion().evaluate(_pages(without_default)).score == 70


def test_hreflang_not_applicable_monolingual() -> None:
    # No hreflang declared -> the criterion is irrelevant (monolingual), not unmeasured.
    result = HreflangCriterion().evaluate(_pages(_page(), _page()))
    assert result.status is Status.NOT_APPLICABLE
