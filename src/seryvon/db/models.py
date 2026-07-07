# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""ORM models (document 05 — data model).

Phase 0: audit-core tables (domain, audit, page, page_signal, criterion_result,
pillar_score, issue, aso_readiness). The citation-tracking, rank-tracking and
competitive-comparison tables (documents 05, 07, 10) are added in their
respective phases.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from seryvon.db.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Domain(Base):
    """Audited domain (document 05, §2.1)."""

    __tablename__ = "domain"

    id: Mapped[uuid.UUID] = _uuid_pk()
    host: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    audits: Mapped[list[Audit]] = relationship(
        back_populates="domain", cascade="all, delete-orphan"
    )


class Audit(Base):
    """Audit run (document 05, §2.2)."""

    __tablename__ = "audit"

    id: Mapped[uuid.UUID] = _uuid_pk()
    domain_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("domain.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_version: Mapped[str] = mapped_column(String(32), nullable=False)
    signal_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    config_digest: Mapped[str | None] = mapped_column(String(64))
    pillars_requested: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    score_global: Mapped[float | None] = mapped_column(Float)
    coverage: Mapped[float] = mapped_column(Float, default=0.0)
    measurement_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    prompt_set: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    domain: Mapped[Domain] = relationship(back_populates="audits")
    pages: Mapped[list[Page]] = relationship(back_populates="audit", cascade="all, delete-orphan")
    criterion_results: Mapped[list[CriterionResultRow]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )
    pillar_scores: Mapped[list[PillarScoreRow]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )
    issues: Mapped[list[IssueRow]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )
    aso_readiness: Mapped[AsoReadinessRow | None] = relationship(
        back_populates="audit", cascade="all, delete-orphan", uselist=False
    )
    artifacts: Mapped[list[ArtifactRow]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )


class Page(Base):
    """Crawled page of an audit (document 05, §2.3)."""

    __tablename__ = "page"

    id: Mapped[uuid.UUID] = _uuid_pk()
    audit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audit.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    render_mode: Mapped[str | None] = mapped_column(String(16))

    audit: Mapped[Audit] = relationship(back_populates="pages")
    signal: Mapped[PageSignalRow | None] = relationship(
        back_populates="page", cascade="all, delete-orphan", uselist=False
    )


class PageSignalRow(Base):
    """A page's signals, JSONB (internal includes the `aso` block, document 05, §2.4)."""

    __tablename__ = "page_signal"

    id: Mapped[uuid.UUID] = _uuid_pk()
    page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("page.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    internal: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    external: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    page: Mapped[Page] = relationship(back_populates="signal")


class CriterionResultRow(Base):
    """Persisted criterion result (document 05, §2.5)."""

    __tablename__ = "criterion_result"

    id: Mapped[uuid.UUID] = _uuid_pk()
    audit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audit.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion_key: Mapped[str] = mapped_column(String(64), nullable=False)
    pillars: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    raw_value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    audit: Mapped[Audit] = relationship(back_populates="criterion_results")


class PillarScoreRow(Base):
    """Aggregated pillar score (document 05, §2.6 — 5 possible values)."""

    __tablename__ = "pillar_score"

    id: Mapped[uuid.UUID] = _uuid_pk()
    audit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audit.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pillar: Mapped[str] = mapped_column(String(8), nullable=False)  # seo/geo/gso/aeo/aso
    score: Mapped[float] = mapped_column(Float, nullable=False)
    measured: Mapped[int] = mapped_column(Integer, default=0)
    excluded: Mapped[int] = mapped_column(Integer, default=0)
    not_applicable: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[float] = mapped_column(Float, default=0.0)
    coverage_label: Mapped[str] = mapped_column(String(16), default="insufficient")

    audit: Mapped[Audit] = relationship(back_populates="pillar_scores")


class IssueRow(Base):
    """Prioritized issue (document 05, §2.7)."""

    __tablename__ = "issue"

    id: Mapped[uuid.UUID] = _uuid_pk()
    audit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audit.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion_key: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    effort: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    priority_bucket: Mapped[str] = mapped_column(String(16), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    # JSON-serializable value that triggered the issue (often a dict — mirrors
    # CriterionResultRow.raw_value). Text would crash on dict adaptation.
    raw_value: Mapped[Any | None] = mapped_column(JSONB)
    affected_pages: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    audit: Mapped[Audit] = relationship(back_populates="issues")


class AsoReadinessRow(Base):
    """Agentic-readiness summary (document 05, §2.8 — NEW TABLE)."""

    __tablename__ = "aso_readiness"

    id: Mapped[uuid.UUID] = _uuid_pk()
    audit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audit.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    readiness_level: Mapped[str] = mapped_column(String(16), nullable=False)
    agent_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    has_webmcp: Mapped[bool] = mapped_column(Boolean, default=False)
    has_action_schema: Mapped[bool] = mapped_column(Boolean, default=False)
    has_agent_forms: Mapped[bool] = mapped_column(Boolean, default=False)
    has_openapi: Mapped[bool] = mapped_column(Boolean, default=False)
    action_signals: Mapped[int] = mapped_column(Integer, default=0)
    ai_discovery_endpoints: Mapped[int] = mapped_column(Integer, default=0)
    has_nlweb: Mapped[bool] = mapped_column(Boolean, default=False)
    brand_coherence_score: Mapped[float | None] = mapped_column(Numeric)
    blocked_agent_bots: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    audit: Mapped[Audit] = relationship(back_populates="aso_readiness")


class ArtifactRow(Base):
    """Object-store metadata for a raw collection artifact (document 05, §4).

    The bytes live in MinIO/S3 under `object_key`; this row is the queryable
    PostgreSQL handle. `audit_id` is the open-core run reference. Content is
    addressed by SHA-256, so `(bucket, object_key)` is unique (dedup).
    """

    __tablename__ = "artifact"
    __table_args__ = (UniqueConstraint("bucket", "object_key", name="uq_artifact_object"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    audit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audit.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compression: Mapped[str] = mapped_column(String(8), default="none")
    encryption: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    audit: Mapped[Audit | None] = relationship(back_populates="artifacts")


class ApiKeyRow(Base):
    """Encrypted BYOK API key (one row per connector, upserted in place).

    The plaintext is never stored; `encrypted_value` is a Fernet token produced
    from `Settings.secret_key`. When that key is absent, this table is inert.
    """

    __tablename__ = "api_key"

    id: Mapped[uuid.UUID] = _uuid_pk()
    connector: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
