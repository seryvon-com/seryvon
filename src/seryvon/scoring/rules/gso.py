# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""GSO pillar rules (Google AI Overviews / AI Mode), document 04 §4.

The **schema-presence** criteria (FAQPage, HowTo, BreadcrumbList, ItemList) are
*site-level*: present on at least one crawled page => 100. A FAQ schema only makes
sense on some pages; a per-page average would wrongly penalize.

`gso.cwv_eligible` derives from the Core Web Vitals (PSI); `gso.longtail` (D6) and
`gso.ai_overview_presence` (SERP API, Phase 4) stay `not_measured`.
"""

from __future__ import annotations

from typing import Any, ClassVar

from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import SignalBundle

# "Good" Core Web Vitals thresholds (Google) for AI Overview eligibility.
_CWV_GOOD = {"lcp": 2500.0, "cls": 0.1, "inp": 200.0}
_JSONLD_SOURCE: dict[str, Any] = {"source": "JSON-LD"}


def _present(
    score: float, key: str, pillars: list[str], weight: float, **fields: Any
) -> CriterionResult:
    """Build a traceable presence result (100/0)."""
    return CriterionResult(
        key=key,
        pillars=pillars,
        score=score,
        status=status_from_score(score),
        evidence=_JSONLD_SOURCE,
        weight=weight,
        **fields,
    )


class _SchemaPresenceCriterion(Criterion):
    """Presence of a JSON-LD schema type on at least one page (site-level)."""

    schema_type: ClassVar[str]
    label: ClassVar[str]

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        pages_with = [p.url for p in signals.pages if self.schema_type in p.structured_data_types]
        score = 100.0 if pages_with else 0.0
        return _present(
            score,
            self.key,
            self.pillars,
            self.weight,
            raw_value={"present": bool(pages_with), "pages": len(pages_with)},
            threshold={"schema": self.schema_type},
            explanation=(
                f"{self.label} présent sur {len(pages_with)} page(s)."
                if pages_with
                else f"{self.label} absent du site."
            ),
        )


@register
class GsoFaqPageCriterion(_SchemaPresenceCriterion):
    """FAQPage schema (`gso.faqpage`)."""

    key = "gso.faqpage"
    pillars: ClassVar[list[str]] = ["gso"]
    weight = 1.3
    schema_type = "FAQPage"
    label = "Schema FAQPage"


@register
class GsoHowToCriterion(_SchemaPresenceCriterion):
    """HowTo schema (`gso.howto`) — also usable by an agent (aso tag)."""

    key = "gso.howto"
    pillars: ClassVar[list[str]] = ["gso", "aso"]
    weight = 0.6
    schema_type = "HowTo"
    label = "Schema HowTo"


@register
class GsoBreadcrumbCriterion(_SchemaPresenceCriterion):
    """BreadcrumbList schema (`gso.breadcrumb`)."""

    key = "gso.breadcrumb"
    pillars: ClassVar[list[str]] = ["gso"]
    weight = 1.0
    schema_type = "BreadcrumbList"
    label = "BreadcrumbList"


@register
class GsoItemListCriterion(Criterion):
    """Structured lists (`gso.itemlist`): ItemList schema or HTML table."""

    key = "gso.itemlist"
    pillars: ClassVar[list[str]] = ["gso"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        present = any(
            "ItemList" in p.structured_data_types or p.tables_count > 0 for p in signals.pages
        )
        score = 100.0 if present else 0.0
        return _present(
            score,
            self.key,
            self.pillars,
            self.weight,
            raw_value={"present": present},
            threshold={"any": "ItemList ou <table>"},
            explanation="Liste/tableau structuré présent."
            if present
            else "Aucune liste structurée.",
        )


@register
class GsoQaFormatCriterion(Criterion):
    """Extractable Q&A format (`gso.qa_format`): FAQPage or question headings."""

    key = "gso.qa_format"
    pillars: ClassVar[list[str]] = ["gso", "aeo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        present = any(
            "FAQPage" in p.structured_data_types or p.question_headings >= 2 for p in signals.pages
        )
        score = 100.0 if present else 0.0
        return _present(
            score,
            self.key,
            self.pillars,
            self.weight,
            raw_value={"present": present},
            threshold={"any": "FAQPage ou ≥2 titres-questions"},
            explanation="Format Q-R extractible présent." if present else "Aucun format Q-R.",
        )


@register
class GsoCwvEligibleCriterion(Criterion):
    """Core Web Vitals eligibility (`gso.cwv_eligible`): all 3 metrics "good"."""

    key = "gso.cwv_eligible"
    pillars: ClassVar[list[str]] = ["gso"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cwv = signals.external.core_web_vitals
        if not cwv or not all(metric in cwv for metric in _CWV_GOOD):
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Core Web Vitals indisponibles (PSI)."
            )
        eligible = all(cwv[metric] <= good for metric, good in _CWV_GOOD.items())
        score = 100.0 if eligible else 0.0
        return _present(
            score,
            self.key,
            self.pillars,
            self.weight,
            raw_value={"core_web_vitals": cwv, "eligible": eligible},
            threshold=dict(_CWV_GOOD),
            explanation="Les 3 Core Web Vitals sont dans les seuils."
            if eligible
            else "Au moins un Core Web Vital hors seuil.",
        )


@register
class GsoLongtailCriterion(Criterion):
    """Long-tail coverage (`gso.longtail`) — `not_measured` in v0.2 (D6)."""

    key = "gso.longtail"
    pillars: ClassVar[list[str]] = ["gso"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        return CriterionResult.not_measured(
            self.key,
            self.pillars,
            self.weight,
            "Longue traîne non mesurable sans données mots-clés/SERP (Phase 4).",
        )


@register
class GsoAiOverviewCriterion(Criterion):
    """AI Overview presence (`gso.ai_overview_presence`) — SERP API, Phase 4."""

    key = "gso.ai_overview_presence"
    pillars: ClassVar[list[str]] = ["gso"]
    weight = 1.5

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        presence = signals.external.ai_overview_presence
        if presence is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "API SERP non configurée (Phase 4)."
            )
        score = round(min(100.0, max(0.0, presence * 100)), 2)
        return _present(
            score,
            self.key,
            self.pillars,
            self.weight,
            raw_value={"ai_overview_presence": presence},
            threshold={"formula": "% prompts avec AI Overview"},
            explanation=f"Présence AI Overview : {score}%.",
        )
