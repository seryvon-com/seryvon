# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Scoring-criterion contract and self-registering registry.

"Rule registry" pattern (document 03, §3.1): each criterion is a class
implementing `Criterion`, decorated with `@register`, that produces a
deterministic `CriterionResult` from a `SignalBundle`. Adding a criterion requires
no change to the engine (requirement O6 — extensibility).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from seryvon.models.enums import Status
from seryvon.models.signals import SignalBundle

#: Per-criterion threshold overrides (the `thresholds:` section of the YAML config),
#: e.g. {"content.depth": {"target_words": 1000}}. Read-only mapping.
ThresholdConfig = Mapping[str, Mapping[str, Any]]


class CriterionResult(BaseModel):
    """Traceable result of a criterion (document 03, §3.1; document 05, §7).

    Every score is explainable: `raw_value` (measured data), `threshold` (applied
    thresholds), `explanation` (human-readable) and `evidence` (source).
    """

    key: str
    pillars: list[str]
    raw_value: Any = None
    score: float
    status: Status
    threshold: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0

    @classmethod
    def not_measured(
        cls,
        key: str,
        pillars: list[str],
        weight: float,
        reason: str,
    ) -> CriterionResult:
        """Build a `not_measured` result (excluded from the computation, renormalized)."""
        return cls(
            key=key,
            pillars=pillars,
            raw_value=None,
            score=0.0,
            status=Status.NOT_MEASURED,
            explanation=reason,
            weight=weight,
        )

    @classmethod
    def not_applicable(
        cls,
        key: str,
        pillars: list[str],
        weight: float,
        reason: str,
    ) -> CriterionResult:
        """Build a `not_applicable` result (excluded AND removed from the coverage base).

        Use when the criterion is irrelevant in this context (e.g. a monolingual
        site for hreflang), as opposed to `not_measured` (data simply unavailable).
        """
        return cls(
            key=key,
            pillars=pillars,
            raw_value=None,
            score=0.0,
            status=Status.NOT_APPLICABLE,
            explanation=reason,
            weight=weight,
        )


class Criterion(ABC):
    """Scoring-criterion interface. Subclass + `@register` to activate it."""

    key: ClassVar[str]
    pillars: ClassVar[list[str]]
    weight: ClassVar[float] = 1.0

    @abstractmethod
    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        """Evaluate the criterion and return a deterministic result.

        `thresholds` carries the threshold overrides (YAML config); `None` =>
        default thresholds. Pure scoring: no I/O, a function of (signals, thresholds).
        """
        raise NotImplementedError


# Global criteria registry, populated by the `@register` decorator.
RULES: dict[str, Criterion] = {}


def register(cls: type[Criterion]) -> type[Criterion]:
    """Decorator: instantiate the criterion and register it by its unique `key`."""
    instance = cls()
    if instance.key in RULES:
        raise ValueError(f"Criterion already registered: {instance.key!r}")
    RULES[instance.key] = instance
    return cls


def clear_registry() -> None:
    """Clear the registry (test utility only)."""
    RULES.clear()
