# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Shared enumerations (statuses, severities, agentic readiness)."""

from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    """Criterion status, derived from the score (document 04, §1.3)."""

    OK = "ok"  # score >= 80
    WARNING = "warning"  # 50 <= score < 80
    CRITICAL = "critical"  # score < 50
    NOT_MEASURED = (
        "not_measured"  # data unavailable -> excluded, but still eligible (lowers coverage)
    )
    NOT_APPLICABLE = "not_applicable"  # criterion irrelevant here -> excluded AND not eligible


class Severity(StrEnum):
    """Severity of an issue (feeds the prioritization, document 04, §7)."""

    WARNING = "warning"
    CRITICAL = "critical"


class ReadinessLevel(StrEnum):
    """Aggregated agentic readiness level (ASO pillar, document 04, §6)."""

    NONE = "none"
    BASIC = "basic"
    READY = "ready"
    ADVANCED = "advanced"


# Score -> status switch thresholds. Centralized for determinism.
STATUS_OK_THRESHOLD = 80.0
STATUS_WARNING_THRESHOLD = 50.0


def status_from_score(score: float) -> Status:
    """Convert a [0-100] score into a status according to the canonical thresholds."""
    if score >= STATUS_OK_THRESHOLD:
        return Status.OK
    if score >= STATUS_WARNING_THRESHOLD:
        return Status.WARNING
    return Status.CRITICAL
