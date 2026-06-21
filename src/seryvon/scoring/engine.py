# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Scoring engine: rule execution, per-pillar aggregation, global score.

Safeguards borrowed from the `scoring.py` pattern (GEO Optimizer, MIT):
- score clamped to [0, 100];
- exclusion of `not_measured` then renormalization of the remaining weights;
- global score = weighted mean of the MEASURED pillars, renormalized.

The computation is fully deterministic: same signals + same config => same scores.
"""

from __future__ import annotations

from seryvon.core.config import DEFAULT_PILLAR_WEIGHTS, AuditConfig
from seryvon.models.criterion import RULES, CriterionResult
from seryvon.models.enums import CoverageLabel, Status
from seryvon.models.report import PillarScore
from seryvon.models.signals import SignalBundle


def _clamp(score: float) -> float:
    """Clamp a score into [0, 100]."""
    return max(0.0, min(100.0, score))


def run_criteria(signals: SignalBundle, config: AuditConfig) -> list[CriterionResult]:
    """Run every registered rule and apply the weight overrides.

    Results are sorted by key for a stable output order (determinism).
    """
    results: list[CriterionResult] = []
    for key in sorted(RULES):
        criterion = RULES[key]
        result = criterion.evaluate(signals, config.thresholds)
        result.score = _clamp(result.score)
        result.evidence_tier = criterion.evidence_tier
        override = config.criteria_overrides.get(key, {})
        if "weight" in override:
            result.weight = float(override["weight"])
        results.append(result)
    return results


def coverage_label(coverage: float) -> CoverageLabel:
    """Map a coverage ratio to its display tier (SIC doc 04 §4)."""
    if coverage >= 0.90:
        return CoverageLabel.COMPLETE
    if coverage >= 0.70:
        return CoverageLabel.SUBSTANTIAL
    if coverage >= 0.40:
        return CoverageLabel.PARTIAL
    return CoverageLabel.INSUFFICIENT


def _coverage(measured: list[CriterionResult], applicable: list[CriterionResult]) -> float:
    """Weight-based coverage: measured weight / applicable (eligible) weight."""
    eligible_weight = sum(r.weight for r in applicable)
    if eligible_weight <= 0:
        return 0.0
    return round(sum(r.weight for r in measured) / eligible_weight, 4)


def score_coverage(results: list[CriterionResult]) -> float:
    """Global coverage over the distinct criteria (excludes `not_applicable` from the base)."""
    applicable = [r for r in results if r.status is not Status.NOT_APPLICABLE]
    measured = [r for r in applicable if r.status is not Status.NOT_MEASURED]
    return _coverage(measured, applicable)


def score_pillar(pillar: str, results: list[CriterionResult]) -> PillarScore:
    """Aggregate a pillar's criteria, excluding `not_measured`/`not_applicable`, and renormalize.

    `coverage` is the measured/eligible weight ratio, where eligible excludes
    `not_applicable` (the criterion does not count against coverage when irrelevant).
    """
    relevant = [r for r in results if pillar in r.pillars]
    applicable = [r for r in relevant if r.status is not Status.NOT_APPLICABLE]
    measured = [r for r in applicable if r.status is not Status.NOT_MEASURED]
    excluded = len(relevant) - len(measured)
    not_applicable = len(relevant) - len(applicable)
    coverage = _coverage(measured, applicable)

    total_weight = sum(r.weight for r in measured)
    if total_weight <= 0:
        return PillarScore(
            pillar=pillar,
            score=0.0,
            measured=0,
            excluded=excluded,
            not_applicable=not_applicable,
            coverage=coverage,
            coverage_label=coverage_label(coverage),
        )

    weighted = sum(r.score * r.weight for r in measured)
    return PillarScore(
        pillar=pillar,
        score=round(weighted / total_weight, 2),
        measured=len(measured),
        excluded=excluded,
        not_applicable=not_applicable,
        coverage=coverage,
        coverage_label=coverage_label(coverage),
    )


def score_global(
    pillar_scores: dict[str, PillarScore],
    config: AuditConfig,
) -> float:
    """Global score = weighted mean of the MEASURED pillars, renormalized.

    A pillar with no measured criterion (measured == 0) is excluded from the
    global score, and the weights of the remaining pillars are renormalized.
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
