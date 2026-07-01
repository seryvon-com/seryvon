# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the on-page AEO rules + geo.ssr."""

from __future__ import annotations

from seryvon.models.enums import Status
from seryvon.models.signals import (
    CitationMetrics,
    ExternalSignals,
    PageSignals,
    SignalBundle,
)
from seryvon.scoring.rules.aeo import (
    AeoAboutPageCriterion,
    AeoAnswerDirectnessCriterion,
    AeoAuthorCredentialsCriterion,
    AeoComparisonTablesCriterion,
    AeoDatesStructuredCriterion,
    AeoDefinedTermsCriterion,
    AeoKgPresenceCriterion,
    AeoLlmCitationCriterion,
)
from seryvon.scoring.rules.geo import GeoSsrCriterion


def _page(url: str = "https://ex.com/", **kwargs: object) -> PageSignals:
    return PageSignals(url=url, **kwargs)  # type: ignore[arg-type]


def _pages(*pages: PageSignals) -> SignalBundle:
    return SignalBundle(domain="ex.com", pages=list(pages))


# --------------------------------------------------------------------------- #
# AEO                                                                          #
# --------------------------------------------------------------------------- #
def test_author_credentials_graded() -> None:
    full = _pages(_page(has_author=True, author_has_credentials=True))
    assert AeoAuthorCredentialsCriterion().evaluate(full).score == 100
    partial = _pages(_page(has_author=True))
    assert AeoAuthorCredentialsCriterion().evaluate(partial).score == 50
    assert AeoAuthorCredentialsCriterion().evaluate(_pages(_page())).score == 0


def test_about_page_detection() -> None:
    home = _page("https://ex.com/")
    about = _page("https://ex.com/a-propos", title="À propos de nous")
    assert AeoAboutPageCriterion().evaluate(_pages(home, about)).score == 100
    assert AeoAboutPageCriterion().evaluate(_pages(home)).score == 0


def test_defined_terms() -> None:
    assert AeoDefinedTermsCriterion().evaluate(_pages(_page(definition_lists_count=1))).score == 100
    schema = _page(structured_data_types=["DefinedTerm"])
    assert AeoDefinedTermsCriterion().evaluate(_pages(schema)).score == 100
    assert AeoDefinedTermsCriterion().evaluate(_pages(_page())).score == 0


def test_dates_structured_is_multipillar() -> None:
    result = AeoDatesStructuredCriterion().evaluate(_pages(_page(has_structured_dates=True)))
    assert result.score == 100
    assert result.pillars == ["aeo", "geo"]


def test_comparison_tables() -> None:
    assert AeoComparisonTablesCriterion().evaluate(_pages(_page(tables_count=2))).score == 100
    assert AeoComparisonTablesCriterion().evaluate(_pages(_page())).score == 0


def test_answer_directness_ratio() -> None:
    bundle = _pages(_page(lead_paragraph_words=40), _page(lead_paragraph_words=5))
    result = AeoAnswerDirectnessCriterion().evaluate(bundle)
    assert result.score == 50.0  # 1 page sur 2 avec accroche suffisante
    assert result.pillars == ["aeo", "gso"]


def test_kg_presence_not_measured_by_default() -> None:
    assert AeoKgPresenceCriterion().evaluate(_pages(_page())).status is Status.NOT_MEASURED
    present = SignalBundle(domain="ex.com", external=ExternalSignals(kg_presence=True))
    assert AeoKgPresenceCriterion().evaluate(present).score == 100


def test_llm_citation_not_measured_by_default() -> None:
    assert AeoLlmCitationCriterion().evaluate(_pages(_page())).status is Status.NOT_MEASURED
    measured = SignalBundle(
        domain="ex.com",
        external=ExternalSignals(
            citation_metrics=CitationMetrics(citation_rate=0.5, engines=["openai", "perplexity"])
        ),
    )
    assert AeoLlmCitationCriterion().evaluate(measured).score == 50.0


# --------------------------------------------------------------------------- #
# GEO (geo.ssr — content parity before JS)                                     #
# --------------------------------------------------------------------------- #
def test_geo_ssr_binary_parity_without_counts() -> None:
    # No word counts (heuristic fallback): parity is binary ssr=1.0 / csr=0.0.
    bundle = _pages(_page(render_mode="ssr"), _page(render_mode="csr"))
    result = GeoSsrCriterion().evaluate(bundle)
    assert result.score == 50.0
    assert result.pillars == ["geo", "aeo", "aso"]


def test_geo_ssr_continuous_parity_rewards_rich_static() -> None:
    # A rich-static page (900/2100 = 0.43 parity) scores far above a thin shell
    # (20/1000 = 0.02), instead of both being a flat 0 under the old binary rule.
    bundle = _pages(
        _page(
            url="https://ex.com/rich/",
            render_mode="csr",
            raw_word_count=900,
            rendered_word_count=2100,
        ),
        _page(
            url="https://ex.com/thin/",
            render_mode="csr",
            raw_word_count=20,
            rendered_word_count=1000,
        ),
    )
    result = GeoSsrCriterion().evaluate(bundle)
    # mean(0.4286, 0.02) * 100 ≈ 22.43
    assert 22 <= result.score <= 23
    assert result.raw_value["csr"] == 2


def test_geo_ssr_parity_caps_at_full() -> None:
    # A page whose raw HTML already has all the content (JS adds nothing) = 100%.
    bundle = _pages(
        _page(
            url="https://ex.com/x/",
            render_mode="ssr",
            raw_word_count=500,
            rendered_word_count=480,
        ),
    )
    result = GeoSsrCriterion().evaluate(bundle)
    assert result.score == 100.0


def test_geo_ssr_not_measured_without_mode() -> None:
    assert GeoSsrCriterion().evaluate(_pages(_page())).status is Status.NOT_MEASURED


def test_geo_ssr_by_route_breakdown() -> None:
    bundle = _pages(
        _page(url="https://ex.com/en/models/a/", render_mode="csr"),
        _page(url="https://ex.com/en/models/b/", render_mode="csr"),
        _page(url="https://ex.com/en/glossary/a/", render_mode="ssr"),
        _page(url="https://ex.com/en/glossary/b/", render_mode="ssr"),
    )
    result = GeoSsrCriterion().evaluate(bundle)
    by_route = result.raw_value["by_route"]
    assert by_route[0] == {"path": "models", "pages": 2, "ssr": 0, "csr": 2}
    assert {"path": "glossary", "pages": 2, "ssr": 2, "csr": 0} in by_route


def test_geo_ssr_top_offenders_sorted_by_parity() -> None:
    # Worst parity first: /b (5/305 = 1.6%) ranks above /a (10/50 = 20%), even
    # though it also has the larger delta here. The SSR page is excluded.
    bundle = _pages(
        _page(
            url="https://ex.com/a/",
            render_mode="csr",
            raw_word_count=10,
            rendered_word_count=50,  # parity 20%, delta 40
        ),
        _page(
            url="https://ex.com/b/",
            render_mode="csr",
            raw_word_count=5,
            rendered_word_count=305,  # parity 2%, delta 300 — worst parity
        ),
        _page(
            url="https://ex.com/c/", render_mode="ssr", raw_word_count=100, rendered_word_count=110
        ),
    )
    result = GeoSsrCriterion().evaluate(bundle)
    offenders = result.raw_value["top_offenders"]
    assert offenders[0] == {
        "url": "https://ex.com/b/",
        "raw_words": 5,
        "rendered_words": 305,
        "delta": 300,
        "parity_pct": 2,
    }
    assert len(offenders) == 2  # the SSR page is excluded
