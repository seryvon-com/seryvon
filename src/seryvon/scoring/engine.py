# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Moteur de scoring : exécution des règles, agrégation par pilier, score global.

Garde-fous repris du pattern de `scoring.py` (GEO Optimizer, MIT) :
- score borné [0, 100] ;
- exclusion des `not_measured` puis renormalisation des poids restants ;
- score global = moyenne pondérée des piliers MESURÉS, renormalisée.

Le calcul est entièrement déterministe : mêmes signaux + même config => mêmes scores.
"""

from __future__ import annotations

from seryvon.core.config import DEFAULT_PILLAR_WEIGHTS, AuditConfig
from seryvon.models.criterion import RULES, CriterionResult
from seryvon.models.enums import Status
from seryvon.models.report import PillarScore
from seryvon.models.signals import SignalBundle


def _clamp(score: float) -> float:
    """Borne un score dans [0, 100]."""
    return max(0.0, min(100.0, score))


def run_criteria(signals: SignalBundle, config: AuditConfig) -> list[CriterionResult]:
    """Exécute toutes les règles enregistrées et applique les surcharges de poids.

    Les résultats sont triés par clé pour un ordre de sortie stable (déterminisme).
    """
    results: list[CriterionResult] = []
    for key in sorted(RULES):
        criterion = RULES[key]
        result = criterion.evaluate(signals)
        result.score = _clamp(result.score)
        override = config.criteria_overrides.get(key, {})
        if "weight" in override:
            result.weight = float(override["weight"])
        results.append(result)
    return results


def score_pillar(pillar: str, results: list[CriterionResult]) -> PillarScore:
    """Agrège les critères d'un pilier en excluant les `not_measured` et renormalise."""
    relevant = [r for r in results if pillar in r.pillars]
    measured = [r for r in relevant if r.status is not Status.NOT_MEASURED]
    excluded = len(relevant) - len(measured)

    total_weight = sum(r.weight for r in measured)
    if total_weight <= 0:
        return PillarScore(pillar=pillar, score=0.0, measured=0, excluded=excluded)

    weighted = sum(r.score * r.weight for r in measured)
    return PillarScore(
        pillar=pillar,
        score=round(weighted / total_weight, 2),
        measured=len(measured),
        excluded=excluded,
    )


def score_global(
    pillar_scores: dict[str, PillarScore],
    config: AuditConfig,
) -> float:
    """Score global = moyenne pondérée des piliers MESURÉS, renormalisée.

    Un pilier sans aucun critère mesuré (measured == 0) est exclu du global,
    et les poids des piliers restants sont renormalisés.
    """
    weights = {**DEFAULT_PILLAR_WEIGHTS, **config.pillar_weights}
    contributing = {
        p: ps for p, ps in pillar_scores.items() if ps.measured > 0 and weights.get(p, 0) > 0
    }
    total_weight = sum(weights[p] for p in contributing)
    if total_weight <= 0:
        return 0.0
    weighted = sum(ps.score * weights[p] for p, ps in contributing.items())
    return round(weighted / total_weight, 2)
