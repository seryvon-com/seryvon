# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""AEO pillar rules (Answer Engine Optimization), document 04 §5.

Measurable on-page criteria (author credibility, About, definitions, dates,
tables, direct answer). `aeo.kg_presence` (Wikidata) is `not_measured` until the
slice-7 connector; `aeo.llm_citation` until M4 (Phase 3).
"""

from __future__ import annotations

from typing import Any, ClassVar

from seryvon.i18n import t
from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import Status, status_from_score
from seryvon.models.signals import PageSignals, SignalBundle

# URL/title hints of an "About / editorial transparency" page.
_ABOUT_HINTS = (
    "about",
    "propos",
    "qui-sommes",
    "qui sommes",
    "notre-histoire",
    "team",
    "equipe",
    "équipe",
    "mentions",
)
_LEAD_MIN_WORDS = 20  # "direct answer" lead paragraph


def _flag(*, key: str, pillars: list[str], weight: float, present: bool) -> CriterionResult:
    """Traceable binary-presence result (100/0)."""
    score = 100.0 if present else 0.0
    return CriterionResult(
        key=key,
        pillars=pillars,
        raw_value={"present": present},
        score=score,
        status=status_from_score(score),
        explanation=t("expl.flag_present") if present else t("expl.flag_absent"),
        evidence={"source": "HTML/JSON-LD"},
        weight=weight,
    )


def _is_about_page(page: PageSignals) -> bool:
    haystack = page.url.lower() + " " + (page.title or "").lower()
    return any(hint in haystack for hint in _ABOUT_HINTS)


@register
class AeoAuthorCredentialsCriterion(Criterion):
    """Author credentials (`aeo.author_credentials`): identifiable + qualified author."""

    key = "aeo.author_credentials"
    pillars: ClassVar[list[str]] = ["aeo"]
    weight = 1.5

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        has_credentials = any(p.author_has_credentials for p in signals.pages)
        has_author = any(p.has_author for p in signals.pages)
        score = 100.0 if has_credentials else 50.0 if has_author else 0.0
        explanation = (
            t("expl.author_full")
            if has_credentials
            else t("expl.author_partial")
            if has_author
            else t("expl.author_none")
        )
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"has_author": has_author, "has_credentials": has_credentials},
            score=score,
            status=status_from_score(score),
            threshold={"complete": "Person + jobTitle/sameAs…"},
            explanation=explanation,
            evidence={"source": "JSON-LD"},
            weight=self.weight,
        )


@register
class AeoAboutPageCriterion(Criterion):
    """Editorial transparency (`aeo.about_page`): presence of an About page."""

    key = "aeo.about_page"
    pillars: ClassVar[list[str]] = ["aeo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        about = next((p.url for p in signals.pages if _is_about_page(p)), None)
        score = 100.0 if about else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"about_page": about},
            score=score,
            status=status_from_score(score),
            threshold={"hint": "URL/titre About / À propos / mentions"},
            explanation=t("expl.about_present", url=about) if about else t("expl.about_absent"),
            evidence={"source": "URL + titre"},
            weight=self.weight,
        )


@register
class AeoDefinedTermsCriterion(Criterion):
    """Atomic definitions (`aeo.defined_terms`): DefinedTerm or <dl> glossary."""

    key = "aeo.defined_terms"
    pillars: ClassVar[list[str]] = ["aeo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        present = any(
            "DefinedTerm" in p.structured_data_types or p.definition_lists_count > 0
            for p in signals.pages
        )
        return _flag(
            key=self.key,
            pillars=self.pillars,
            weight=self.weight,
            present=present,
        )


@register
class AeoDatesStructuredCriterion(Criterion):
    """Structured dates (`aeo.dates_structured`): datePublished/dateModified (geo tag)."""

    key = "aeo.dates_structured"
    pillars: ClassVar[list[str]] = ["aeo", "geo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        present = any(p.has_structured_dates for p in signals.pages)
        return _flag(
            key=self.key,
            pillars=self.pillars,
            weight=self.weight,
            present=present,
        )


@register
class AeoComparisonTablesCriterion(Criterion):
    """Comparison tables (`aeo.comparison_tables`)."""

    key = "aeo.comparison_tables"
    pillars: ClassVar[list[str]] = ["aeo"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        pages_with_tables = [p for p in signals.pages if p.tables_count > 0]
        present = len(pages_with_tables) > 0
        # Detect compare pages that exist but have no static <table> (JS-rendered).
        # Only count pages explicitly under a /compare/ path to avoid false positives
        # from research pages whose titles happen to contain "-vs-".
        compare_pages = [
            p for p in signals.pages if "/compare/" in p.url or "/compare-models" in p.url
        ]
        js_only = not present and len(compare_pages) > 0
        if js_only:
            explanation = t(
                "expl.comparison_tables_js",
                compare_count=len(compare_pages),
            )
        elif present:
            explanation = t(
                "expl.comparison_tables_present",
                page_count=len(pages_with_tables),
            )
        else:
            explanation = t("expl.comparison_tables_absent")
        n_tables = len(pages_with_tables)
        n_compare = len(compare_pages)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages_with_tables": n_tables, "compare_pages": n_compare},
            score=100.0 if present else 0.0,
            status=Status.OK if present else Status.CRITICAL,
            threshold={"required": "≥1 page with <table>"},
            explanation=explanation,
            evidence={"source": "HTML <table> tags + /compare URL pattern"},
            weight=self.weight,
        )


@register
class AeoAnswerDirectnessCriterion(Criterion):
    """Direct answers (`aeo.answer_directness`): lead answer paragraph up top (gso tag)."""

    key = "aeo.answer_directness"
    pillars: ClassVar[list[str]] = ["aeo", "gso"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        direct = sum(1 for p in pages if p.lead_paragraph_words >= _LEAD_MIN_WORDS)
        score = round(direct / len(pages) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages), "with_lead": direct},
            score=score,
            status=status_from_score(score),
            threshold={"min_lead_words": _LEAD_MIN_WORDS},
            explanation=t(
                "expl.answer_directness", non_direct=len(pages) - direct, total=len(pages)
            ),
            evidence={"source": "HTML parsing"},
            weight=self.weight,
        )


@register
class AeoKgPresenceCriterion(Criterion):
    """Knowledge-graph presence (`aeo.kg_presence`) — Wikidata.

    `not_measured` until the Wikidata connector is wired (slice 7). Tags geo + aso:
    the KG entity is what an agent resolves first.
    """

    key = "aeo.kg_presence"
    pillars: ClassVar[list[str]] = ["aeo", "geo", "aso"]
    weight = 1.5

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        kg = signals.external.kg_presence
        if kg is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.wikidata_not_configured")
            )
        return _flag(
            key=self.key,
            pillars=self.pillars,
            weight=self.weight,
            present=kg,
        )


@register
class AeoLlmCitationCriterion(Criterion):
    """Citation by answer engines (`aeo.llm_citation`) — measured by M4 (Phase 3).

    Reads the aggregated *retrieval citation* (`external.citation_metrics.citation_rate`),
    a signal shared with `geo.citation_rate` but attached to the AEO pillar.
    """

    key = "aeo.llm_citation"
    pillars: ClassVar[list[str]] = ["aeo"]
    weight = 2.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None:
            return CriterionResult.not_measured(
                self.key,
                self.pillars,
                self.weight,
                t("reason.citation_unavailable"),
            )
        score = round(cm.citation_rate * 100, 2)
        raw: dict[str, Any] = {"citation_rate": cm.citation_rate, "engines": cm.engines}
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value=raw,
            score=score,
            status=status_from_score(score),
            threshold={"formula": "% réponses retrieval citant le domaine"},
            explanation=t("expl.aeo_llm_citation", score=score),
            evidence={
                "source": "M4 citation tracking",
                "per_engine": {k: v.model_dump() for k, v in cm.per_engine.items()},
            },
            weight=self.weight,
        )
