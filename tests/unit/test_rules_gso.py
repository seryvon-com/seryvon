# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the on-page GSO rules (schema presence, Q&A, CWV eligibility)."""

from __future__ import annotations

from seryvon.models.enums import Status
from seryvon.models.signals import ExternalSignals, PageSignals, SignalBundle
from seryvon.scoring.rules.gso import (
    GsoAiOverviewCriterion,
    GsoBreadcrumbCriterion,
    GsoCwvEligibleCriterion,
    GsoFaqPageCriterion,
    GsoHowToCriterion,
    GsoItemListCriterion,
    GsoLongtailCriterion,
    GsoQaFormatCriterion,
)


def _page(url: str = "https://ex.com/", **kwargs: object) -> PageSignals:
    return PageSignals(url=url, **kwargs)  # type: ignore[arg-type]


def _pages(*pages: PageSignals) -> SignalBundle:
    return SignalBundle(domain="ex.com", pages=list(pages))


def test_faqpage_presence() -> None:
    present = _pages(_page(structured_data_types=["FAQPage"]))
    assert GsoFaqPageCriterion().evaluate(present).score == 100
    assert GsoFaqPageCriterion().evaluate(_pages(_page())).score == 0


def test_howto_is_multipillar_gso_aso() -> None:
    result = GsoHowToCriterion().evaluate(_pages(_page(structured_data_types=["HowTo"])))
    assert result.score == 100
    assert result.pillars == ["gso", "aso"]


def test_breadcrumb_presence() -> None:
    present = _pages(_page(structured_data_types=["BreadcrumbList"]))
    assert GsoBreadcrumbCriterion().evaluate(present).score == 100


def test_itemlist_schema_or_table() -> None:
    assert (
        GsoItemListCriterion().evaluate(_pages(_page(structured_data_types=["ItemList"]))).score
        == 100
    )
    assert GsoItemListCriterion().evaluate(_pages(_page(tables_count=1))).score == 100
    assert GsoItemListCriterion().evaluate(_pages(_page())).score == 0


def test_qa_format_faqpage_or_questions() -> None:
    assert (
        GsoQaFormatCriterion().evaluate(_pages(_page(structured_data_types=["FAQPage"]))).score
        == 100
    )
    assert GsoQaFormatCriterion().evaluate(_pages(_page(question_headings=2))).score == 100
    result = GsoQaFormatCriterion().evaluate(_pages(_page(question_headings=1)))
    assert result.score == 0
    assert result.pillars == ["gso", "aeo"]


def test_cwv_eligible() -> None:
    good = SignalBundle(
        domain="ex.com",
        external=ExternalSignals(core_web_vitals={"lcp": 2000, "cls": 0.05, "inp": 150}),
    )
    assert GsoCwvEligibleCriterion().evaluate(good).score == 100
    bad = SignalBundle(
        domain="ex.com",
        external=ExternalSignals(core_web_vitals={"lcp": 5000, "cls": 0.05, "inp": 150}),
    )
    assert GsoCwvEligibleCriterion().evaluate(bad).score == 0


def test_cwv_eligible_not_measured_without_data() -> None:
    assert GsoCwvEligibleCriterion().evaluate(_pages(_page())).status is Status.NOT_MEASURED
    partial = SignalBundle(domain="ex.com", external=ExternalSignals(core_web_vitals={"lcp": 2000}))
    assert GsoCwvEligibleCriterion().evaluate(partial).status is Status.NOT_MEASURED


def test_longtail_and_ai_overview_not_measured() -> None:
    assert GsoLongtailCriterion().evaluate(_pages(_page())).status is Status.NOT_MEASURED
    assert GsoAiOverviewCriterion().evaluate(_pages(_page())).status is Status.NOT_MEASURED


def test_ai_overview_score_when_present() -> None:
    # Rule ready for the SERP connector (Phase 4): presence -> %.
    bundle = SignalBundle(domain="ex.com", external=ExternalSignals(ai_overview_presence=0.6))
    assert GsoAiOverviewCriterion().evaluate(bundle).score == 60.0


def test_schema_presence_not_measured_without_pages() -> None:
    empty = SignalBundle(domain="ex.com", pages=[])
    assert GsoFaqPageCriterion().evaluate(empty).status is Status.NOT_MEASURED
