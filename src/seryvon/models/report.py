# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Audit report models (JSON source of truth — document 05, §7)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import ReadinessLevel, Severity


class PillarScore(BaseModel):
    """Aggregated score of a pillar, with measured/excluded counts + coverage."""

    pillar: str
    score: float
    measured: int = 0
    excluded: int = 0
    not_applicable: int = 0
    coverage: float = 0.0  # measured / eligible weight (excludes not_applicable)


class Issue(BaseModel):
    """Prioritized issue (document 04, §7: (impact × severity) / effort)."""

    criterion_key: str
    severity: Severity
    impact: int
    effort: int
    priority_score: float
    priority_bucket: str  # P1 / P2 / P3 / P4
    recommendation: str = ""
    affected_pages: list[str] = Field(default_factory=list)
    affected_pillars: int = 0  # informational only (not a priority multiplier, review §13)


class AsoReadiness(BaseModel):
    """Agentic-readiness summary (table `aso_readiness`, document 05, §2.8)."""

    readiness_level: ReadinessLevel = ReadinessLevel.NONE
    agent_ready: bool = False
    has_webmcp: bool = False
    has_action_schema: bool = False
    ai_discovery_endpoints: int = 0
    has_nlweb: bool = False
    brand_coherence_score: float | None = None
    blocked_agent_bots: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    """Complete report of an audit (serialized to JSON, source of truth)."""

    domain: str
    tool_version: str
    schema_version: int
    started_at: datetime
    finished_at: datetime | None = None

    score_global: float = 0.0
    coverage: float = 0.0  # global measured / eligible weight over distinct criteria
    pillars: dict[str, PillarScore] = Field(default_factory=dict)

    criteria: list[CriterionResult] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    aso_readiness: AsoReadiness | None = None

    config_digest: str | None = None
