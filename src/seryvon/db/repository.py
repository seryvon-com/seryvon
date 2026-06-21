# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Repository layer: persisting and reloading audit reports (M8).

Maps the `AuditReport` (Pydantic, source of truth) to/from the ORM rows
(document 05). Outside the pure `run_audit` pipeline (decision DB3): persistence
is opt-in and never touches scoring. Pages/signals are not persisted here (the
report does not carry them; a re-scoring snapshot is a backlog improvement).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from seryvon.db import models as m
from seryvon.models.artifact import ArtifactRef, ArtifactType, Compression
from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import ReadinessLevel, Severity, Status
from seryvon.models.report import AsoReadiness, AuditReport, Issue, PillarScore


@dataclass(slots=True)
class AuditSummary:
    """Audit summary for the history (without the criteria detail)."""

    audit_id: uuid.UUID
    domain: str
    score_global: float | None
    started_at: datetime


def _get_or_create_domain(session: Session, host: str) -> m.Domain:
    domain = session.scalar(select(m.Domain).where(m.Domain.host == host))
    if domain is None:
        domain = m.Domain(host=host)
        session.add(domain)
        session.flush()
    return domain


def persist_report(report: AuditReport, session: Session) -> uuid.UUID:
    """Persist a report (domain + audit + criteria/pillars/issues/readiness)."""
    domain = _get_or_create_domain(session, report.domain)
    audit = m.Audit(
        domain_id=domain.id,
        tool_version=report.tool_version,
        signal_schema_version=report.schema_version,
        config_digest=report.config_digest,
        pillars_requested=list(report.pillars),
        score_global=report.score_global,
        started_at=report.started_at,
        finished_at=report.finished_at,
    )
    audit.criterion_results = [
        m.CriterionResultRow(
            criterion_key=c.key,
            pillars=list(c.pillars),
            raw_value=c.raw_value,
            score=c.score,
            status=c.status.value,
            threshold=c.threshold,
            explanation=c.explanation,
            evidence=c.evidence,
            weight=c.weight,
        )
        for c in report.criteria
    ]
    audit.pillar_scores = [
        m.PillarScoreRow(
            pillar=ps.pillar, score=ps.score, measured=ps.measured, excluded=ps.excluded
        )
        for ps in report.pillars.values()
    ]
    audit.issues = [
        m.IssueRow(
            criterion_key=i.criterion_key,
            severity=i.severity.value,
            impact=i.impact,
            effort=i.effort,
            priority_score=i.priority_score,
            priority_bucket=i.priority_bucket,
            recommendation=i.recommendation,
            affected_pages=list(i.affected_pages),
        )
        for i in report.issues
    ]
    audit.artifacts = [
        m.ArtifactRow(
            project_id=a.project_id,
            run_id=a.run_id,
            type=a.type.value,
            bucket=a.bucket,
            object_key=a.object_key,
            sha256=a.sha256,
            mime_type=a.mime_type,
            size_bytes=a.size_bytes,
            compression=a.compression.value,
            encryption=a.encryption,
            retention_until=a.retention_until,
        )
        for a in report.artifacts
    ]
    if report.aso_readiness is not None:
        r = report.aso_readiness
        audit.aso_readiness = m.AsoReadinessRow(
            readiness_level=r.readiness_level.value,
            agent_ready=r.agent_ready,
            has_webmcp=r.has_webmcp,
            has_action_schema=r.has_action_schema,
            ai_discovery_endpoints=r.ai_discovery_endpoints,
            has_nlweb=r.has_nlweb,
            brand_coherence_score=r.brand_coherence_score,
            blocked_agent_bots=list(r.blocked_agent_bots),
        )
    session.add(audit)
    session.flush()
    return audit.id


def load_report(session: Session, audit_id: uuid.UUID) -> AuditReport | None:
    """Rebuild an `AuditReport` from the database (None if not found)."""
    audit = session.get(m.Audit, audit_id)
    if audit is None:
        return None

    criteria = [
        CriterionResult(
            key=row.criterion_key,
            pillars=list(row.pillars),
            raw_value=row.raw_value,
            score=row.score,
            status=Status(row.status),
            threshold=row.threshold,
            explanation=row.explanation,
            evidence=row.evidence,
            weight=row.weight,
        )
        for row in sorted(audit.criterion_results, key=lambda r: r.criterion_key)
    ]
    issues = [
        Issue(
            criterion_key=row.criterion_key,
            severity=Severity(row.severity),
            impact=row.impact,
            effort=row.effort,
            priority_score=row.priority_score,
            priority_bucket=row.priority_bucket,
            recommendation=row.recommendation,
            affected_pages=list(row.affected_pages),
        )
        for row in sorted(audit.issues, key=lambda r: (-r.priority_score, r.criterion_key))
    ]
    pillars = {
        ps.pillar: PillarScore(
            pillar=ps.pillar, score=ps.score, measured=ps.measured, excluded=ps.excluded
        )
        for ps in audit.pillar_scores
    }
    readiness = None
    if audit.aso_readiness is not None:
        ar = audit.aso_readiness
        brand = ar.brand_coherence_score
        readiness = AsoReadiness(
            readiness_level=ReadinessLevel(ar.readiness_level),
            agent_ready=ar.agent_ready,
            has_webmcp=ar.has_webmcp,
            has_action_schema=ar.has_action_schema,
            ai_discovery_endpoints=ar.ai_discovery_endpoints,
            has_nlweb=ar.has_nlweb,
            brand_coherence_score=float(brand) if brand is not None else None,
            blocked_agent_bots=list(ar.blocked_agent_bots),
        )

    artifacts = [
        ArtifactRef(
            project_id=row.project_id,
            run_id=row.run_id,
            type=ArtifactType(row.type),
            bucket=row.bucket,
            object_key=row.object_key,
            sha256=row.sha256,
            mime_type=row.mime_type,
            size_bytes=row.size_bytes,
            compression=Compression(row.compression),
            encryption=row.encryption,
            retention_until=row.retention_until,
            created_at=row.created_at,
        )
        for row in sorted(audit.artifacts, key=lambda r: r.object_key)
    ]

    return AuditReport(
        domain=audit.domain.host,
        tool_version=audit.tool_version,
        schema_version=audit.signal_schema_version,
        started_at=audit.started_at,
        finished_at=audit.finished_at,
        score_global=audit.score_global or 0.0,
        pillars=pillars,
        criteria=criteria,
        issues=issues,
        aso_readiness=readiness,
        config_digest=audit.config_digest,
        artifacts=artifacts,
    )


def list_audits(session: Session, host: str) -> list[AuditSummary]:
    """Audit history of a domain, most recent first."""
    rows = session.scalars(
        select(m.Audit)
        .join(m.Domain)
        .where(m.Domain.host == host)
        .order_by(m.Audit.started_at.desc())
    )
    return [
        AuditSummary(
            audit_id=a.id,
            domain=host,
            score_global=a.score_global,
            started_at=a.started_at,
        )
        for a in rows
    ]
