# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests des règles AEO on-page + geo.ssr."""

from __future__ import annotations

from seryvon.models.enums import Status
from seryvon.models.signals import ExternalSignals, PageSignals, SignalBundle
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
        domain="ex.com", external=ExternalSignals(llm_citations={"openai": 0.4, "perplexity": 0.6})
    )
    assert AeoLlmCitationCriterion().evaluate(measured).score == 50.0


# --------------------------------------------------------------------------- #
# GEO (geo.ssr via heuristique)                                               #
# --------------------------------------------------------------------------- #
def test_geo_ssr_ratio() -> None:
    bundle = _pages(_page(render_mode="ssr"), _page(render_mode="csr"))
    result = GeoSsrCriterion().evaluate(bundle)
    assert result.score == 50.0
    assert result.pillars == ["geo", "aeo", "aso"]


def test_geo_ssr_not_measured_without_mode() -> None:
    assert GeoSsrCriterion().evaluate(_pages(_page())).status is Status.NOT_MEASURED
