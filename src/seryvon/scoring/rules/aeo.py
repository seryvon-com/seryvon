# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Règles du pilier AEO (Answer Engine Optimization), document 04 §5.

Critères on-page mesurables (crédibilité auteur, About, définitions, dates,
tableaux, réponse directe). `aeo.kg_presence` (Wikidata) est `not_measured`
jusqu'au connecteur de la slice 7 ; `aeo.llm_citation` jusqu'au M4 (Phase 3).
"""

from __future__ import annotations

from typing import Any, ClassVar

from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import PageSignals, SignalBundle

# Indices d'URL/titre d'une page « À propos / transparence éditoriale ».
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
_LEAD_MIN_WORDS = 20  # paragraphe d'accroche « réponse directe »


def _flag(
    *, key: str, pillars: list[str], weight: float, present: bool, label: str
) -> CriterionResult:
    """Résultat de présence binaire (100/0) traçable."""
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
    """Credentials d'auteur (`aeo.author_credentials`) : auteur identifiable + qualifié."""

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
    """Transparence éditoriale (`aeo.about_page`) : présence d'une page À propos."""

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
    """Définitions atomiques (`aeo.defined_terms`) : DefinedTerm ou glossaire <dl>."""

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
    """Dates structurées (`aeo.dates_structured`) : datePublished/dateModified (tag geo)."""

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
    """Tableaux comparatifs (`aeo.comparison_tables`)."""

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
    """Réponses directes (`aeo.answer_directness`) : paragraphe-réponse en tête (tag gso)."""

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
    """Présence dans le graphe de connaissances (`aeo.kg_presence`) — Wikidata.

    `not_measured` tant que le connecteur Wikidata n'est pas câblé (slice 7).
    Tags geo + aso : l'entité KG est ce qu'un agent résout en premier.
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
    """Citation par les answer engines (`aeo.llm_citation`) — mesuré par M4 (Phase 3)."""

    key = "aeo.llm_citation"
    pillars: ClassVar[list[str]] = ["aeo"]
    weight = 2.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        citations = signals.external.llm_citations
        if not citations:
            return CriterionResult.not_measured(
                self.key,
                self.pillars,
                self.weight,
                "Citation tracking LLM non disponible (Phase 3).",
            )
        rate = sum(citations.values()) / len(citations)
        score = round(min(100.0, max(0.0, rate * 100)), 2)
        raw: dict[str, Any] = {"llm_citations": dict(citations)}
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value=raw,
            score=score,
            status=status_from_score(score),
            threshold={"formula": "% citation moyen sur answer engines"},
            explanation=f"Taux de citation answer engines : {score}%.",
            evidence={"source": "M4 citation tracking"},
            weight=self.weight,
        )
