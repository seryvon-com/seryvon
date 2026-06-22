# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""REST API (FastAPI).

`/health`, then the persisted audit cycle: `POST /audits` runs and **persists** an
audit (`Location: /audits/{id}` header), `GET /audits/{id}` reloads a report,
`GET /audits?domain=…` returns a domain's history. Asynchronous execution via
Celery (status/polling) comes in slice B3.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import Any, TypedDict

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, HttpUrl
from sqlalchemy.orm import Session

from seryvon import __version__
from seryvon.citation.connector import LlmConnector
from seryvon.citation.engines import AnthropicConnector, GeminiConnector, OpenAiConnector
from seryvon.citation.perplexity import PerplexityConnector
from seryvon.citation.tracking import run_tracking
from seryvon.core.audit import run_audit
from seryvon.core.config import AuditConfig, Settings, get_settings
from seryvon.core.crypto import EncryptionError, decrypt_value, encrypt_value, mask_value
from seryvon.db import repository
from seryvon.db.base import session_scope
from seryvon.models.prompts import Prompt, PromptIntent, PromptSet, ThemeProfile
from seryvon.models.report import AuditReport
from seryvon.models.signals import CitationMetrics
from seryvon.scoring import (
    ComparisonMode,
    ComparisonResult,
    IncomparableError,
    compare_scorecards,
)

# ---------------------------------------------------------------------------
# Async job stores (in-process; upgrade to Redis/Celery for multi-worker)
# ---------------------------------------------------------------------------


class _AuditJob(TypedDict):
    status: str
    audit_id: str | None
    error: str | None


class _CitationJob(TypedDict):
    status: str
    metrics: dict[str, Any] | None
    error: str | None


_audit_jobs: dict[str, _AuditJob] = {}
_citation_jobs: dict[str, _CitationJob] = {}

# Hard ceiling for a single audit (discovery + crawl + connectors + scoring).
_AUDIT_TIMEOUT_SECONDS = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(
    title="Seryvon API",
    version=__version__,
    summary="Deterministic SEO / GEO / GSO / AEO / ASO audit.",
)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: a transactional session per request."""
    with session_scope() as session:
        yield session


class AuditRequest(BaseModel):
    """Request body to launch an audit."""

    url: HttpUrl
    locale: str = "en"  # produced-text locale (en base, fr second); presentation only


class AuditSummaryOut(BaseModel):
    """Audit summary for the history."""

    model_config = ConfigDict(from_attributes=True)

    audit_id: uuid.UUID
    domain: str
    score_global: float | None
    started_at: datetime


class CompareRequest(BaseModel):
    """Request body to compare two persisted scorecards (M6, SIC doc 06 §5)."""

    left_run_id: uuid.UUID
    right_run_id: uuid.UUID
    mode: ComparisonMode = ComparisonMode.STRICT


class KeyOut(BaseModel):
    """BYOK key status for a connector (plaintext never returned)."""

    connector: str
    masked_value: str | None  # None when source is "none"
    source: str  # "db" | "env" | "none"
    created_at: datetime | None
    updated_at: datetime | None


class KeyIn(BaseModel):
    """Request body to store a BYOK key."""

    value: str


class AuditTaskOut(BaseModel):
    """Response for async audit submission (202 Accepted)."""

    task_id: str
    status_url: str


class AuditTaskStatus(BaseModel):
    """Polling response for an async audit job."""

    status: str  # pending | running | done | failed
    audit_id: str | None = None
    error: str | None = None


class CitationRequest(BaseModel):
    """Request body to launch LLM citation tracking."""

    domain: str
    brand: str | None = None
    competitors: list[str] = []


class CitationTaskOut(BaseModel):
    """Response for async citation-tracking submission (202 Accepted)."""

    task_id: str
    status_url: str


class CitationTaskStatus(BaseModel):
    """Polling response for an async citation-tracking job."""

    status: str  # pending | running | done | failed
    metrics: dict[str, Any] | None = None
    error: str | None = None


def _encryption_guard() -> str:
    """Return SERYVON_SECRET_KEY or raise 503."""
    sk = get_settings().secret_key
    if not sk:
        raise HTTPException(
            status_code=503,
            detail="BYOK encryption not configured — set SERYVON_SECRET_KEY",
        )
    return sk


def _connector_key_out(connector: str, session: Session) -> KeyOut:
    """Build KeyOut for one connector: DB key takes precedence over env var."""
    settings = get_settings()
    field = repository.CONNECTOR_FIELD[connector]
    env_val: str = getattr(settings, field, "")
    sk = settings.secret_key
    row = repository.get_key_encrypted(session, connector)
    if row is not None and sk:
        try:
            plain = decrypt_value(sk, row)
            masked: str | None = mask_value(plain)
        except EncryptionError:
            masked = "***"
        db_row_obj = next(
            (r for r in repository.list_keys(session) if r.connector == connector), None
        )
        return KeyOut(
            connector=connector,
            masked_value=masked,
            source="db",
            created_at=db_row_obj.created_at if db_row_obj else None,
            updated_at=db_row_obj.updated_at if db_row_obj else None,
        )
    if env_val:
        return KeyOut(
            connector=connector,
            masked_value=mask_value(env_val),
            source="env",
            created_at=None,
            updated_at=None,
        )
    return KeyOut(
        connector=connector, masked_value=None, source="none", created_at=None, updated_at=None
    )


def _build_connectors(settings: Settings) -> list[LlmConnector]:
    """Build the list of active LLM connectors from configured BYOK keys."""
    connectors: list[LlmConnector] = []
    if settings.perplexity_api_key:
        connectors.append(PerplexityConnector(api_key=settings.perplexity_api_key))
    if settings.openai_api_key:
        connectors.append(OpenAiConnector(api_key=settings.openai_api_key))
    if settings.anthropic_api_key:
        connectors.append(AnthropicConnector(api_key=settings.anthropic_api_key))
    if settings.gemini_api_key:
        connectors.append(GeminiConnector(api_key=settings.gemini_api_key))
    return connectors


def _minimal_prompt_set(domain: str, brand: str | None, competitors: list[str]) -> PromptSet:
    """Build a minimal, generic prompt set for citation tracking without crawling."""
    b = brand or domain
    prompts = [
        Prompt(text=f"What is {domain}?", intent=PromptIntent.DEFINITIONAL, quality_score=0.8),
        Prompt(text=f"Tell me about {b}", intent=PromptIntent.DEFINITIONAL, quality_score=0.7),
        Prompt(text=f"Should I use {b}?", intent=PromptIntent.RECOMMENDATION, quality_score=0.7),
        Prompt(text=f"How does {b} work?", intent=PromptIntent.EXPLANATORY, quality_score=0.7),
        Prompt(
            text=f"What are the best alternatives to {b}?",
            intent=PromptIntent.COMPARATIVE,
            quality_score=0.6,
        ),
    ]
    return PromptSet(
        domain=domain,
        generated_by="api",
        theme_profile=ThemeProfile(domain=domain, brand=b),
        prompts=prompts,
        tracked_competitors=list(competitors),
    )


def _resolve_settings(session: Session) -> Settings:
    """Merge env settings with DB-stored keys (DB fills gaps, env takes precedence)."""
    base = get_settings()
    sk = base.secret_key
    if not sk:
        return base
    overrides: dict[str, str] = {}
    for connector, field in repository.CONNECTOR_FIELD.items():
        if not getattr(base, field, ""):
            encrypted = repository.get_key_encrypted(session, connector)
            if encrypted:
                with contextlib.suppress(EncryptionError):
                    overrides[field] = decrypt_value(sk, encrypted)
    return base.model_copy(update=overrides) if overrides else base


async def _run_audit_job(task_id: str, url: str, locale: str, settings: Settings) -> None:
    """Background coroutine: run audit, persist, update job store."""
    _audit_jobs[task_id]["status"] = "running"
    try:
        config = AuditConfig.default()
        config.locale = locale
        report = await asyncio.wait_for(
            run_audit(url, config, settings=settings),
            timeout=_AUDIT_TIMEOUT_SECONDS,
        )
        with session_scope() as session:
            audit_id = repository.persist_report(report, session)
        _audit_jobs[task_id] = {"status": "done", "audit_id": str(audit_id), "error": None}
    except TimeoutError:
        _audit_jobs[task_id] = {
            "status": "failed",
            "audit_id": None,
            "error": f"Audit timed out after {_AUDIT_TIMEOUT_SECONDS}s",
        }
    except Exception as exc:
        _audit_jobs[task_id] = {"status": "failed", "audit_id": None, "error": str(exc)}


async def _run_citation_job(
    task_id: str,
    domain: str,
    brand: str | None,
    competitors: list[str],
    settings: Settings,
) -> None:
    """Background coroutine: run LLM citation tracking, update job store."""
    _citation_jobs[task_id]["status"] = "running"
    try:
        connectors = _build_connectors(settings)
        if not connectors:
            raise ValueError("No LLM API keys configured — add them via /keys")
        prompt_set = _minimal_prompt_set(domain, brand, competitors)
        metrics: CitationMetrics | None = await run_tracking(
            prompt_set,
            connectors,
            target_domain=domain,
            brand=brand,
            competitors=competitors,
            repetitions=2,
        )
        if metrics is None:
            raise ValueError("No LLM responses collected")
        _citation_jobs[task_id] = {
            "status": "done",
            "metrics": metrics.model_dump(mode="json"),
            "error": None,
        }
    except Exception as exc:
        _citation_jobs[task_id] = {"status": "failed", "metrics": None, "error": str(exc)}


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}


@app.post("/audits", status_code=202, response_model=AuditTaskOut)
async def create_audit(
    request: AuditRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    session: Session = Depends(get_session),
) -> AuditTaskOut:
    """Submit an audit asynchronously. Poll /audits/tasks/{task_id} for completion."""
    task_id = str(uuid.uuid4())
    settings = _resolve_settings(session)
    _audit_jobs[task_id] = {"status": "pending", "audit_id": None, "error": None}
    background_tasks.add_task(_run_audit_job, task_id, str(request.url), request.locale, settings)
    response.headers["Location"] = f"/audits/tasks/{task_id}"
    return AuditTaskOut(task_id=task_id, status_url=f"/audits/tasks/{task_id}")


@app.get("/audits/tasks/{task_id}", response_model=AuditTaskStatus)
def get_audit_task(task_id: str) -> AuditTaskStatus:
    """Poll the status of an async audit job."""
    job = _audit_jobs.get(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return AuditTaskStatus(**job)


@app.get("/audits/{audit_id}", response_model=AuditReport)
def get_audit(audit_id: uuid.UUID, session: Session = Depends(get_session)) -> AuditReport:
    """Reload a persisted audit report (404 if not found)."""
    report = repository.load_report(session, audit_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    return report


@app.get("/audits/{audit_id}/prompt-set", response_model=PromptSet)
def get_prompt_set(audit_id: uuid.UUID, session: Session = Depends(get_session)) -> PromptSet:
    """Return the deterministic prompt set generated during the audit (M4b, doc 08)."""
    report = repository.load_report(session, audit_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    if report.prompt_set is None:
        raise HTTPException(status_code=404, detail="Prompt set not available for this audit")
    return report.prompt_set


@app.get("/keys", response_model=list[KeyOut])
def list_keys(session: Session = Depends(get_session)) -> list[KeyOut]:
    """Return BYOK key status for all connectors (plaintext never exposed)."""
    return [_connector_key_out(c, session) for c in repository.CONNECTOR_FIELD]


@app.put("/keys/{connector}", response_model=KeyOut)
def upsert_key(connector: str, body: KeyIn, session: Session = Depends(get_session)) -> KeyOut:
    """Store or update an encrypted BYOK key for a connector."""
    if connector not in repository.CONNECTOR_FIELD:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector}")
    sk = _encryption_guard()
    value = body.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Key value must not be empty")
    encrypted = encrypt_value(sk, value)
    repository.upsert_key(session, connector, encrypted)
    return _connector_key_out(connector, session)


@app.delete("/keys/{connector}", status_code=204)
def delete_key(connector: str, session: Session = Depends(get_session)) -> None:
    """Delete a stored BYOK key for a connector."""
    if connector not in repository.CONNECTOR_FIELD:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector}")
    _encryption_guard()
    found = repository.delete_key(session, connector)
    if not found:
        raise HTTPException(status_code=404, detail=f"No stored key for: {connector}")


@app.get("/audits", response_model=list[AuditSummaryOut])
def list_audits(
    domain: str, session: Session = Depends(get_session)
) -> list[repository.AuditSummary]:
    """Audit history of a domain (most recent first)."""
    return repository.list_audits(session, domain)


@app.post("/citations", status_code=202, response_model=CitationTaskOut)
async def create_citation_tracking(
    request: CitationRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    session: Session = Depends(get_session),
) -> CitationTaskOut:
    """Submit LLM citation tracking (async). Poll /citations/tasks/{task_id}."""
    task_id = str(uuid.uuid4())
    settings = _resolve_settings(session)
    _citation_jobs[task_id] = {"status": "pending", "metrics": None, "error": None}
    background_tasks.add_task(
        _run_citation_job,
        task_id,
        request.domain,
        request.brand,
        request.competitors,
        settings,
    )
    response.headers["Location"] = f"/citations/tasks/{task_id}"
    return CitationTaskOut(task_id=task_id, status_url=f"/citations/tasks/{task_id}")


@app.get("/citations/tasks/{task_id}", response_model=CitationTaskStatus)
def get_citation_task(task_id: str) -> CitationTaskStatus:
    """Poll the status of an async citation-tracking job."""
    job = _citation_jobs.get(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return CitationTaskStatus(**job)


@app.post("/scorecards/compare", response_model=ComparisonResult)
def compare(request: CompareRequest, session: Session = Depends(get_session)) -> ComparisonResult:
    """Compare two persisted scorecards (M6, SIC doc 06 §5).

    404 if either run is unknown; 409 (RFC 9457 problem detail) when the requested
    mode is stricter than the measurement profiles allow.
    """
    left = repository.load_report(session, request.left_run_id)
    right = repository.load_report(session, request.right_run_id)
    if left is None or right is None:
        missing = request.left_run_id if left is None else request.right_run_id
        raise HTTPException(status_code=404, detail=f"Scorecard not found: {missing}")
    try:
        return compare_scorecards(left, right, request.mode)
    except IncomparableError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type": "https://seryvon.dev/problems/incompatible-measurement-profile",
                "title": "Measurement profiles are incompatible",
                "status": 409,
                "detail": str(exc),
                "instance": "/scorecards/compare",
                "extensions": {
                    "comparability": exc.comparability.value,
                    "differences": exc.differences,
                    "allowed_modes": [m.value for m in exc.allowed_modes],
                },
            },
        ) from exc
