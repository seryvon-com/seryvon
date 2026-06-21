# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Scorecard comparison (M6, SIC docs 04 §7 + 06 §5).

Two audit results are comparable only as far as their measurement profiles allow.
The classification (SIC doc 04 §7) is computed from the hashed profiles:

- `exact`        : identical profile digest.
- `compatible`   : differences allowed by a versioned rule (e.g. a pure version bump).
- `intersection` : scores recomputed on the criteria common to both runs.
- `incompatible` : comparison forbidden — only a descriptive side-by-side is allowed.

The requested `mode` (strict/intersection/descriptive) states what the caller will
accept; if the computed comparability is weaker than the mode requires, the caller
gets a 409 (handled at the API layer). This module is pure and deterministic.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from seryvon import PILLARS
from seryvon.core.config import AuditConfig
from seryvon.models.enums import Status
from seryvon.models.report import AuditReport, MeasurementProfile
from seryvon.scoring.engine import score_global, score_pillar


class Comparability(StrEnum):
    """Computed comparability between two measurement profiles (doc 04 §7)."""

    EXACT = "exact"
    COMPATIBLE = "compatible"
    INTERSECTION = "intersection"
    INCOMPATIBLE = "incompatible"


class ComparisonMode(StrEnum):
    """Comparison the caller is willing to accept (doc 06 §5)."""

    STRICT = "strict"  # require exact or compatible
    INTERSECTION = "intersection"  # allow recompute on common criteria
    DESCRIPTIVE = "descriptive"  # side-by-side only, always allowed


# Profile fields, partitioned by their effect on comparability. A difference in a
# BREAKING field changes the meaning of the scores -> incompatible. A difference in
# an INTERSECTION field only changes which criteria were measured -> recompute on
# the common set. COMPATIBLE fields are cosmetic (versioned-rule allowance).
_COMPATIBLE_FIELDS = frozenset({"seryvon_version"})
_INTERSECTION_FIELDS = frozenset({"active_connectors", "criteria_overrides"})
_BREAKING_FIELDS = frozenset(
    {"signal_schema_version", "rule_catalog_digest", "pillar_weights", "thresholds"}
)
_PROFILE_FIELDS = _COMPATIBLE_FIELDS | _INTERSECTION_FIELDS | _BREAKING_FIELDS


class CriterionDelta(BaseModel):
    """Per-criterion score difference (right - left)."""

    key: str
    left_score: float | None
    right_score: float | None
    delta: float | None
    left_status: Status | None
    right_status: Status | None


class PillarDelta(BaseModel):
    """Per-pillar score difference (right - left)."""

    pillar: str
    left_score: float | None
    right_score: float | None
    delta: float | None


class ComparisonResult(BaseModel):
    """Outcome of comparing two scorecards."""

    comparability: Comparability
    requested_mode: ComparisonMode
    allowed_modes: list[ComparisonMode]
    profile_differences: list[str]
    recomputed: bool = False  # True when scores were re-derived on the common criteria
    common_criteria: list[str] = Field(default_factory=list)
    global_delta: float | None = None
    left_global: float | None = None
    right_global: float | None = None
    pillars: list[PillarDelta] = Field(default_factory=list)
    criteria: list[CriterionDelta] = Field(default_factory=list)


def _profile_differences(left: MeasurementProfile, right: MeasurementProfile) -> list[str]:
    """Sorted list of profile fields that differ between the two runs."""
    return sorted(f for f in _PROFILE_FIELDS if getattr(left, f) != getattr(right, f))


def classify(
    left: MeasurementProfile, right: MeasurementProfile
) -> tuple[Comparability, list[str]]:
    """Classify comparability from the two profiles (doc 04 §7)."""
    if left.digest == right.digest:
        return Comparability.EXACT, []
    diffs = _profile_differences(left, right)
    if any(d in _BREAKING_FIELDS for d in diffs):
        return Comparability.INCOMPATIBLE, diffs
    if any(d in _INTERSECTION_FIELDS for d in diffs):
        return Comparability.INTERSECTION, diffs
    if diffs and all(d in _COMPATIBLE_FIELDS for d in diffs):
        return Comparability.COMPATIBLE, diffs
    # Digests differ but no tracked field does (e.g. an untracked profile field):
    # stay safe and require an intersection recompute.
    return Comparability.INTERSECTION, diffs


def _allowed_modes(comparability: Comparability) -> list[ComparisonMode]:
    if comparability in (Comparability.EXACT, Comparability.COMPATIBLE):
        return [ComparisonMode.STRICT, ComparisonMode.INTERSECTION, ComparisonMode.DESCRIPTIVE]
    if comparability is Comparability.INTERSECTION:
        return [ComparisonMode.INTERSECTION, ComparisonMode.DESCRIPTIVE]
    return [ComparisonMode.DESCRIPTIVE]


def _measured_keys(report: AuditReport) -> set[str]:
    """Criterion keys that actually carry a score (excludes not_measured/applicable)."""
    excluded = {Status.NOT_MEASURED, Status.NOT_APPLICABLE}
    return {c.key for c in report.criteria if c.status not in excluded}


def _recompute_over(report: AuditReport, keys: set[str]) -> tuple[float, dict[str, float]]:
    """Recompute the global + per-pillar scores restricted to `keys`."""
    subset = [c for c in report.criteria if c.key in keys]
    pillars = {p: score_pillar(p, subset) for p in PILLARS}
    weights = report.measurement_profile.pillar_weights if report.measurement_profile else {}
    overall = score_global(pillars, AuditConfig(pillar_weights=dict(weights)))
    return overall, {p: ps.score for p, ps in pillars.items()}


def _criterion_deltas(
    left: AuditReport, right: AuditReport, keys: set[str]
) -> list[CriterionDelta]:
    left_by = {c.key: c for c in left.criteria}
    right_by = {c.key: c for c in right.criteria}
    deltas: list[CriterionDelta] = []
    for key in sorted(keys):
        lc = left_by.get(key)
        rc = right_by.get(key)
        ls = lc.score if lc else None
        rs = rc.score if rc else None
        delta = round(rs - ls, 2) if ls is not None and rs is not None else None
        deltas.append(
            CriterionDelta(
                key=key,
                left_score=ls,
                right_score=rs,
                delta=delta,
                left_status=lc.status if lc else None,
                right_status=rc.status if rc else None,
            )
        )
    return deltas


def _pillar_deltas(left: dict[str, float], right: dict[str, float]) -> list[PillarDelta]:
    deltas: list[PillarDelta] = []
    for pillar in PILLARS:
        ls = left.get(pillar)
        rs = right.get(pillar)
        delta = round(rs - ls, 2) if ls is not None and rs is not None else None
        deltas.append(PillarDelta(pillar=pillar, left_score=ls, right_score=rs, delta=delta))
    return deltas


def compare_scorecards(
    left: AuditReport,
    right: AuditReport,
    mode: ComparisonMode = ComparisonMode.STRICT,
) -> ComparisonResult:
    """Compare two scorecards under the requested mode.

    Raises `IncomparableError` when the requested mode is stricter than the
    computed comparability allows (e.g. `strict` over incompatible profiles).
    """
    if left.measurement_profile is None or right.measurement_profile is None:
        raise IncomparableError(
            Comparability.INCOMPATIBLE,
            mode,
            ["measurement_profile"],
            [ComparisonMode.DESCRIPTIVE],
        )

    comparability, diffs = classify(left.measurement_profile, right.measurement_profile)
    allowed = _allowed_modes(comparability)
    if mode not in allowed:
        raise IncomparableError(comparability, mode, diffs, allowed)

    result = ComparisonResult(
        comparability=comparability,
        requested_mode=mode,
        allowed_modes=allowed,
        profile_differences=diffs,
        left_global=left.score_global,
        right_global=right.score_global,
    )

    # Descriptive: side-by-side, no recomputation, no delta (incomparable scores).
    if mode is ComparisonMode.DESCRIPTIVE and comparability is Comparability.INCOMPATIBLE:
        result.pillars = _pillar_deltas(
            {p: ps.score for p, ps in left.pillars.items()},
            {p: ps.score for p, ps in right.pillars.items()},
        )
        for pd in result.pillars:
            pd.delta = None
        return result

    if mode is ComparisonMode.INTERSECTION or comparability is Comparability.INTERSECTION:
        common = _measured_keys(left) & _measured_keys(right)
        left_global, left_pillars = _recompute_over(left, common)
        right_global, right_pillars = _recompute_over(right, common)
        result.recomputed = True
        result.common_criteria = sorted(common)
        result.left_global = left_global
        result.right_global = right_global
        result.global_delta = round(right_global - left_global, 2)
        result.pillars = _pillar_deltas(left_pillars, right_pillars)
        result.criteria = _criterion_deltas(left, right, common)
        return result

    # Exact / compatible under strict mode: direct delta over the union of criteria.
    result.global_delta = round((right.score_global or 0.0) - (left.score_global or 0.0), 2)
    result.pillars = _pillar_deltas(
        {p: ps.score for p, ps in left.pillars.items()},
        {p: ps.score for p, ps in right.pillars.items()},
    )
    all_keys = {c.key for c in left.criteria} | {c.key for c in right.criteria}
    result.criteria = _criterion_deltas(left, right, all_keys)
    return result


class IncomparableError(Exception):
    """Requested mode is stricter than the profiles allow (maps to HTTP 409)."""

    def __init__(
        self,
        comparability: Comparability,
        requested_mode: ComparisonMode,
        differences: list[str],
        allowed_modes: list[ComparisonMode],
    ) -> None:
        self.comparability = comparability
        self.requested_mode = requested_mode
        self.differences = differences
        self.allowed_modes = allowed_modes
        super().__init__(
            f"profiles are {comparability.value}; mode {requested_mode.value} not allowed"
        )
