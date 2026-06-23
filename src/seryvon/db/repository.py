# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Repository layer: persisting/reloading audit reports (M8) + BYOK key CRUD.

Maps the `AuditReport` (Pydantic, source of truth) to/from the ORM rows
(document 05). Outside the pure `run_audit` pipeline (decision DB3): persistence
is opt-in and never touches scoring. Pages/signals are not persisted here (the
report does not carry them; a re-scoring snapshot is a backlog improvement).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from seryvon.db import models as m
from seryvon.models.artifact import ArtifactRef, ArtifactType, Compression
from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import CoverageLabel, ReadinessLevel, Severity, Status
from seryvon.models.prompts import PromptSet
from seryvon.models.report import (
    AsoReadiness,
    AuditReport,
    Issue,
    MeasurementProfile,
    PillarScore,
)


@dataclass(slots=True)
class AuditSummary:
    """Audit summary for the history (without the criteria detail)."""

    audit_id: uuid.UUID
    domain: str
    score_global: float | None
    started_at: datetime
    criteria_measured: int = 0


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
        coverage=report.coverage,
        measurement_profile=(
            report.measurement_profile.model_dump()
            if report.measurement_profile is not None
            else None
        ),
        prompt_set=(
            report.prompt_set.model_dump(mode="json") if report.prompt_set is not None else None
        ),
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
            pillar=ps.pillar,
            score=ps.score,
            measured=ps.measured,
            excluded=ps.excluded,
            not_applicable=ps.not_applicable,
            coverage=ps.coverage,
            coverage_label=ps.coverage_label.value,
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
            pillar=ps.pillar,
            score=ps.score,
            measured=ps.measured,
            excluded=ps.excluded,
            not_applicable=ps.not_applicable,
            coverage=ps.coverage,
            coverage_label=CoverageLabel(ps.coverage_label),
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
        coverage=audit.coverage,
        measurement_profile=(
            MeasurementProfile(**audit.measurement_profile)
            if audit.measurement_profile is not None
            else None
        ),
        prompt_set=(
            PromptSet.model_validate(audit.prompt_set) if audit.prompt_set is not None else None
        ),
        pillars=pillars,
        criteria=criteria,
        issues=issues,
        aso_readiness=readiness,
        config_digest=audit.config_digest,
        artifacts=artifacts,
    )


# ---------------------------------------------------------------------------
# BYOK key CRUD
# ---------------------------------------------------------------------------

#: Connectors that support BYOK keys (maps connector name → Settings field).
CONNECTOR_FIELD: dict[str, str] = {
    "psi": "psi_api_key",
    "opr": "opr_api_key",
    "dataforseo": "dataforseo_api_key",
    "perplexity": "perplexity_api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "gemini": "gemini_api_key",
    "serp": "serp_api_key",
    "gsc": "gsc_service_account",
}


def upsert_key(session: Session, connector: str, encrypted_value: bytes) -> m.ApiKeyRow:
    """Create or update an encrypted API key for a connector."""
    from datetime import UTC

    row = session.scalar(select(m.ApiKeyRow).where(m.ApiKeyRow.connector == connector))
    if row is None:
        row = m.ApiKeyRow(connector=connector, encrypted_value=encrypted_value)
        session.add(row)
    else:
        row.encrypted_value = encrypted_value
        from datetime import datetime

        row.updated_at = datetime.now(UTC)
    session.flush()
    return row


def get_key_encrypted(session: Session, connector: str) -> bytes | None:
    """Return the raw Fernet token for a connector, or None if not stored."""
    row = session.scalar(select(m.ApiKeyRow).where(m.ApiKeyRow.connector == connector))
    return row.encrypted_value if row is not None else None


def list_keys(session: Session) -> list[m.ApiKeyRow]:
    """Return all stored API key rows, sorted by connector name."""
    return list(session.scalars(select(m.ApiKeyRow).order_by(m.ApiKeyRow.connector)))


def delete_key(session: Session, connector: str) -> bool:
    """Delete a stored API key. Returns True if a row was deleted."""
    row = session.scalar(select(m.ApiKeyRow).where(m.ApiKeyRow.connector == connector))
    if row is None:
        return False
    session.delete(row)
    return True


def list_audits(session: Session, host: str) -> list[AuditSummary]:
    """Audit history of a domain, most recent first."""
    _NOT_SCORED = ("not_measured", "not_applicable")
    measured_sq = (
        select(
            m.CriterionResultRow.audit_id,
            func.count().label("cnt"),
        )
        .where(m.CriterionResultRow.status.notin_(_NOT_SCORED))
        .group_by(m.CriterionResultRow.audit_id)
        .subquery()
    )
    rows = session.execute(
        select(m.Audit, func.coalesce(measured_sq.c.cnt, 0).label("criteria_measured"))
        .join(m.Domain)
        .outerjoin(measured_sq, measured_sq.c.audit_id == m.Audit.id)
        .where(m.Domain.host == host)
        .order_by(m.Audit.started_at.desc())
    )
    return [
        AuditSummary(
            audit_id=a.id,
            domain=host,
            score_global=a.score_global,
            started_at=a.started_at,
            criteria_measured=int(cnt),
        )
        for a, cnt in rows
    ]
