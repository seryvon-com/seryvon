# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Règles de performance (Core Web Vitals + Lighthouse), alimentées par PSI.

Critères `perf.*` du document 04 §2. Ils ne lisent que `signals.external`
(rempli par le connecteur PageSpeed Insights) ; absents => `not_measured`
(jamais d'estimation). Seuils = bandes officielles Google (good / needs-
improvement / poor). Tag `gso` ajouté en Phase 2 ; seo seul en Phase 1.
"""

from __future__ import annotations

from typing import Any, ClassVar

from seryvon.models.criterion import Criterion, CriterionResult, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import SignalBundle

_PSI_SOURCE: dict[str, Any] = {"source": "PageSpeed Insights (CrUX field data)"}


class CoreWebVitalCriterion(Criterion):
    """Base d'un Core Web Vital : 100 si ≤ `good`, 50 si ≤ `poor`, 0 sinon."""

    metric: ClassVar[str]
    good: ClassVar[float]
    poor: ClassVar[float]
    unit: ClassVar[str] = ""

    def evaluate(self, signals: SignalBundle) -> CriterionResult:
        cwv = signals.external.core_web_vitals
        value = cwv.get(self.metric) if cwv else None
        if value is None:
            return CriterionResult.not_measured(
                self.key,
                self.pillars,
                self.weight,
                f"{self.metric.upper()} indisponible (PSI ou données terrain absentes).",
            )
        if value <= self.good:
            score = 100.0
        elif value <= self.poor:
            score = 50.0
        else:
            score = 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={self.metric: value, "unit": self.unit},
            score=score,
            status=status_from_score(score),
            threshold={"good": self.good, "poor": self.poor},
            explanation=f"{self.metric.upper()} = {value}{self.unit} (seuil bon ≤ {self.good}).",
            evidence=_PSI_SOURCE,
            weight=self.weight,
        )


@register
class PerfLcpCriterion(CoreWebVitalCriterion):
    """Largest Contentful Paint (`perf.lcp`) : bon ≤ 2500 ms."""

    key = "perf.lcp"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.5
    metric = "lcp"
    good = 2500.0
    poor = 4000.0
    unit = "ms"


@register
class PerfClsCriterion(CoreWebVitalCriterion):
    """Cumulative Layout Shift (`perf.cls`) : bon ≤ 0.1."""

    key = "perf.cls"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.2
    metric = "cls"
    good = 0.1
    poor = 0.25


@register
class PerfInpCriterion(CoreWebVitalCriterion):
    """Interaction to Next Paint (`perf.inp`) : bon ≤ 200 ms."""

    key = "perf.inp"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.2
    metric = "inp"
    good = 200.0
    poor = 500.0
    unit = "ms"


@register
class PerfLighthouseCriterion(Criterion):
    """Score de performance Lighthouse (`perf.lighthouse`) : score labo ×100."""

    key = "perf.lighthouse"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0

    def evaluate(self, signals: SignalBundle) -> CriterionResult:
        raw = signals.external.lighthouse_performance
        if raw is None:
            return CriterionResult.not_measured(
                self.key,
                self.pillars,
                self.weight,
                "Score Lighthouse indisponible (PSI non configuré).",
            )
        score = round(min(100.0, max(0.0, raw * 100)), 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"lighthouse_performance": raw},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "score Lighthouse ×100"},
            explanation=f"Score de performance Lighthouse : {score}/100.",
            evidence={"source": "PageSpeed Insights (Lighthouse lab)"},
            weight=self.weight,
        )
