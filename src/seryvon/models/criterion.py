# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Contrat des critères de scoring et registre auto-enregistré.

Pattern « Rule registry » (document 03, §3.1) : chaque critère est une classe
implémentant `Criterion`, décorée par `@register`, qui produit un `CriterionResult`
déterministe à partir d'un `SignalBundle`. L'ajout d'un critère ne requiert aucune
modification du moteur (exigence O6 — extensibilité).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from seryvon.models.enums import Status
from seryvon.models.signals import SignalBundle


class CriterionResult(BaseModel):
    """Résultat traçable d'un critère (document 03, §3.1 ; document 05, §7).

    Chaque score est explicable : `raw_value` (donnée mesurée), `threshold`
    (seuils appliqués), `explanation` (lisible) et `evidence` (source).
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
        """Construit un résultat `not_measured` (exclu du calcul, renormalisé)."""
        return cls(
            key=key,
            pillars=pillars,
            raw_value=None,
            score=0.0,
            status=Status.NOT_MEASURED,
            explanation=reason,
            weight=weight,
        )


class Criterion(ABC):
    """Interface d'un critère de scoring. Sous-classe + `@register` pour l'activer."""

    key: ClassVar[str]
    pillars: ClassVar[list[str]]
    weight: ClassVar[float] = 1.0

    @abstractmethod
    def evaluate(self, signals: SignalBundle) -> CriterionResult:
        """Évalue le critère sur les signaux et renvoie un résultat déterministe."""
        raise NotImplementedError


# Registre global des critères, peuplé par le décorateur `@register`.
RULES: dict[str, Criterion] = {}


def register(cls: type[Criterion]) -> type[Criterion]:
    """Décorateur : instancie le critère et l'enregistre par sa `key` unique."""
    instance = cls()
    if instance.key in RULES:
        raise ValueError(f"Critère déjà enregistré : {instance.key!r}")
    RULES[instance.key] = instance
    return cls


def clear_registry() -> None:
    """Vide le registre (utilitaire de test uniquement)."""
    RULES.clear()
