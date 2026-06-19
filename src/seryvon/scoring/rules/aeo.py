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

from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import status_from_score
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


def _flag(
    *, key: str, pillars: list[str], weight: float, present: bool, label: str
) -> CriterionResult:
    """Traceable binary-presence result (100/0)."""
    score = 100.0 if present else 0.0
    return CriterionResult(
        key=key,
        pillars=pillars,
        raw_value={"present": present},
        score=score,
        status=status_from_score(score),
        explanation=f"{label} : {'présent' if present else 'absent'}.",
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
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        has_credentials = any(p.author_has_credentials for p in signals.pages)
        has_author = any(p.has_author for p in signals.pages)
        score = 100.0 if has_credentials else 50.0 if has_author else 0.0
        explanation = (
            "Auteur identifiable avec credentials."
            if has_credentials
            else "Auteur identifiable sans credentials structurés."
            if has_author
            else "Aucun auteur identifiable."
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
                self.key, self.pillars, self.weight, "Aucune page crawlée."
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
            explanation=f"Page About : {about}" if about else "Aucune page About détectée.",
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
                self.key, self.pillars, self.weight, "Aucune page crawlée."
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
            label="Définitions (DefinedTerm / <dl>)",
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
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        present = any(p.has_structured_dates for p in signals.pages)
        return _flag(
            key=self.key,
            pillars=self.pillars,
            weight=self.weight,
            present=present,
            label="Dates structurées",
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
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        present = any(p.tables_count > 0 for p in signals.pages)
        return _flag(
            key=self.key,
            pillars=self.pillars,
            weight=self.weight,
            present=present,
            label="Tableau comparatif",
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
                self.key, self.pillars, self.weight, "Aucune page crawlée."
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
            explanation=f"{direct}/{len(pages)} page(s) avec paragraphe-réponse en tête.",
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
                self.key, self.pillars, self.weight, "Wikidata non configuré (slice ultérieure)."
            )
        return _flag(
            key=self.key,
            pillars=self.pillars,
            weight=self.weight,
            present=kg,
            label="Entité Wikidata/Wikipedia",
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
                "Citation tracking LLM non disponible (clé API BYOK requise).",
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
            explanation=f"Taux de citation answer engines : {score}%.",
            evidence={
                "source": "M4 citation tracking",
                "per_engine": {k: v.model_dump() for k, v in cm.per_engine.items()},
            },
            weight=self.weight,
        )
