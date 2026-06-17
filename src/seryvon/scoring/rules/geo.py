# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Règles du pilier GEO (Generative Engine Optimization), document 04 §3.

Phase 2 : seul `geo.ssr` est mesurable on-page, depuis l'heuristique render_mode
de M2 (décision D10 ; la mesure fiable par rendu Playwright viendra plus tard).
Le reste du pilier GEO (densité d'entités, fraîcheur, citation LLM…) arrive en
Phase 3. `geo.ssr` est multi-piliers : un agent (ASO) et un answer engine (AEO)
doivent parser le contenu sans exécuter de JS.
"""

from __future__ import annotations

from typing import ClassVar

from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import SignalBundle


@register
class GeoSsrCriterion(Criterion):
    """Rendu SSR vs CSR (`geo.ssr`) : part des pages servies en rendu serveur."""

    key = "geo.ssr"
    pillars: ClassVar[list[str]] = ["geo", "aeo", "aso"]
    weight = 1.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        modes = [p.render_mode for p in signals.pages if p.render_mode]
        if not modes:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Mode de rendu indisponible."
            )
        ssr = sum(1 for mode in modes if mode == "ssr")
        score = round(ssr / len(modes) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(modes), "ssr": ssr},
            score=score,
            status=status_from_score(score),
            threshold={"target": "100% SSR"},
            explanation=f"{ssr}/{len(modes)} page(s) en rendu serveur (heuristique M2).",
            evidence={"source": "heuristique SSR/CSR (M2)"},
            weight=self.weight,
        )
