# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Integration tests for the repository (real Postgres, gated by env var).

Cleanly skipped if `SERYVON_TEST_DATABASE_URL` is absent (PG types: no SQLite).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from seryvon.db import repository
from seryvon.db.base import Base
from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import ReadinessLevel, Severity, Status
from seryvon.models.report import AsoReadiness, AuditReport, Issue, PillarScore

_TEST_DB = os.environ.get("SERYVON_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not _TEST_DB, reason="SERYVON_TEST_DATABASE_URL not set (Postgres required)"
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(_TEST_DB, future=True)  # type: ignore[arg-type]
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    with maker() as sess:
        yield sess
    Base.metadata.drop_all(engine)
    engine.dispose()


def _report(domain: str = "example.com", score: float = 64.8) -> AuditReport:
    return AuditReport(
        domain=domain,
        tool_version="0.1.0.dev0",
        schema_version=7,
        started_at=datetime(2026, 6, 18, 9, 0, tzinfo=UTC),
        finished_at=datetime(2026, 6, 18, 9, 1, tzinfo=UTC),
        score_global=score,
        pillars={
            "seo": PillarScore(pillar="seo", score=72.1, measured=20, excluded=6),
            "geo": PillarScore(pillar="geo", score=0.0, measured=0, excluded=0),
        },
        criteria=[
            CriterionResult(
                key="authority.backlinks",
                pillars=["seo"],
                raw_value=None,  # not_measured -> JSONB null
                score=0.0,
                status=Status.NOT_MEASURED,
                explanation="Aucune source.",
                weight=1.0,
            ),
            CriterionResult(
                key="meta.title",
                pillars=["seo"],
                raw_value={"pages": 1, "passing": 1},
                score=100.0,
                status=Status.OK,
                threshold={"min": 30, "max": 60},
                explanation="Title conforme.",
                evidence={"source": "HTML"},
                weight=1.5,
            ),
        ],
        issues=[
            Issue(
                criterion_key="meta.description",
                severity=Severity.CRITICAL,
                impact=2,
                effort=1,
                priority_score=4.0,
                priority_bucket="P1",
                recommendation="Rédiger une meta description.",
            )
        ],
        aso_readiness=AsoReadiness(
            readiness_level=ReadinessLevel.BASIC,
            has_action_schema=True,
            ai_discovery_endpoints=2,
            brand_coherence_score=62.0,
            blocked_agent_bots=["GPTBot"],
        ),
        config_digest="abc123",
    )


def test_persist_and_load_roundtrip(session: Session) -> None:
    report = _report()
    audit_id = repository.persist_report(report, session)
    session.commit()
    session.expunge_all()  # force a real reload from the database

    loaded = repository.load_report(session, audit_id)
    assert loaded is not None
    assert loaded.model_dump() == report.model_dump()


def test_load_unknown_returns_none(session: Session) -> None:
    assert repository.load_report(session, uuid.uuid4()) is None


def test_list_audits_orders_recent_first(session: Session) -> None:
    repository.persist_report(_report(score=50.0), session)
    repository.persist_report(_report(score=80.0), session)
    session.commit()

    summaries = repository.list_audits(session, "example.com")
    assert len(summaries) == 2
    assert {s.score_global for s in summaries} == {50.0, 80.0}
    assert all(s.domain == "example.com" for s in summaries)
