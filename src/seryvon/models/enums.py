# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Énumérations partagées (statuts, sévérités, readiness agentique)."""

from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    """Statut d'un critère, dérivé du score (document 04, §1.3)."""

    OK = "ok"  # score >= 80
    WARNING = "warning"  # 50 <= score < 80
    CRITICAL = "critical"  # score < 50
    NOT_MEASURED = "not_measured"  # donnée indisponible -> exclu du calcul


class Severity(StrEnum):
    """Sévérité d'un problème (alimente la priorisation, document 04, §7)."""

    WARNING = "warning"
    CRITICAL = "critical"


class ReadinessLevel(StrEnum):
    """Niveau de readiness agentique agrégé (pilier ASO, document 04, §6)."""

    NONE = "none"
    BASIC = "basic"
    READY = "ready"
    ADVANCED = "advanced"


# Seuils de bascule score -> statut. Centralisés pour le déterminisme.
STATUS_OK_THRESHOLD = 80.0
STATUS_WARNING_THRESHOLD = 50.0


def status_from_score(score: float) -> Status:
    """Convertit un score [0-100] en statut selon les seuils canoniques."""
    if score >= STATUS_OK_THRESHOLD:
        return Status.OK
    if score >= STATUS_WARNING_THRESHOLD:
        return Status.WARNING
    return Status.CRITICAL
