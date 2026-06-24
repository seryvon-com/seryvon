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
`GET /audits?domain=…` returns a domain's history. Async execution via Celery
(Phase 6): tasks are dispatched to CPU/IO queues and polled via AsyncResult.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from celery.result import AsyncResult
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, HttpUrl
from sqlalchemy.orm import Session

from seryvon import __version__
from seryvon.core.config import get_settings
from seryvon.core.crypto import EncryptionError, decrypt_value, encrypt_value, mask_value
from seryvon.db import repository
from seryvon.db.base import session_scope
from seryvon.models.prompts import PromptSet
from seryvon.models.report import AuditReport
from seryvon.scoring import (
    ComparisonMode,
    ComparisonResult,
    IncomparableError,
    compare_scorecards,
)
from seryvon.tasks.app import celery_app
from seryvon.tasks.audit import run_audit_task
from seryvon.tasks.citation import run_citation_task

log = logging.getLogger(__name__)

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


@app.middleware("http")
async def api_key_middleware(request: Request, call_next: Any) -> Any:
    """Enforce X-API-Key when SERYVON_API_KEY is configured.

    Unauthenticated requests to any route other than GET /health return 401.
    When SERYVON_API_KEY is empty (default), all requests pass through —
    suitable for local dev / docker-compose without a reverse proxy.
    """
    required = get_settings().api_key
    if required and request.url.path != "/health":
        provided = request.headers.get("X-API-Key", "")
        if provided != required:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid X-API-Key header"},
            )
    return await call_next(request)


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
    criteria_measured: int = 0


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
    logs: list[str] = []


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


def _audit_task_status(task_id: str) -> AuditTaskStatus:
    """Map a Celery AsyncResult to AuditTaskStatus."""
    r = AsyncResult(task_id, app=celery_app)
    if r.state == "SUCCESS":
        result: dict[str, Any] = r.result or {}
        return AuditTaskStatus(
            status="done",
            audit_id=result.get("audit_id"),
            logs=result.get("logs", []),
        )
    if r.state == "FAILURE":
        return AuditTaskStatus(status="failed", error=str(r.result))
    if r.state in ("STARTED", "PROGRESS"):
        meta: dict[str, Any] = r.info or {}
        return AuditTaskStatus(status="running", logs=meta.get("logs", []))
    return AuditTaskStatus(status="pending")


def _citation_task_status(task_id: str) -> CitationTaskStatus:
    """Map a Celery AsyncResult to our CitationTaskStatus schema."""
    r = AsyncResult(task_id, app=celery_app)
    if r.state == "SUCCESS":
        return CitationTaskStatus(status="done", metrics=r.result)
    if r.state == "FAILURE":
        return CitationTaskStatus(status="failed", error=str(r.result))
    if r.state == "STARTED":
        return CitationTaskStatus(status="running")
    return CitationTaskStatus(status="pending")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}


@app.get("/audits/cost-estimate")
def audit_cost_estimate(session: Session = Depends(get_session)) -> dict[str, object]:
    """Return an indicative cost breakdown for one audit based on active BYOK keys."""
    from seryvon.core.audit_cost import estimate_audit_cost
    from seryvon.core.settings_resolver import resolve_settings

    settings = resolve_settings(session)
    return estimate_audit_cost(settings).as_dict()


@app.post("/audits", status_code=202, response_model=AuditTaskOut)
def create_audit(request: AuditRequest, response: Response) -> AuditTaskOut:
    """Submit an audit asynchronously via Celery CPU queue. Poll /audits/tasks/{task_id}."""
    result = run_audit_task.delay(str(request.url), request.locale)
    response.headers["Location"] = f"/audits/tasks/{result.id}"
    return AuditTaskOut(task_id=result.id, status_url=f"/audits/tasks/{result.id}")


@app.get("/audits/tasks/{task_id}", response_model=AuditTaskStatus)
def get_audit_task(task_id: str) -> AuditTaskStatus:
    """Poll the status of an async audit job (Celery AsyncResult)."""
    return _audit_task_status(task_id)


@app.get("/audits/{audit_id}", response_model=AuditReport)
def get_audit(audit_id: uuid.UUID, session: Session = Depends(get_session)) -> AuditReport:
    """Reload a persisted audit report (404 if not found)."""
    report = repository.load_report(session, audit_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    return report


@app.get("/audits/{audit_id}/report.pdf")
def get_audit_pdf(audit_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    """Render a persisted audit as a PDF file (requires seryvon[pdf])."""
    from seryvon.reporting.pdf_report import report_to_pdf

    report = repository.load_report(session, audit_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    try:
        pdf_bytes = report_to_pdf(report)
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="PDF export not available — install WeasyPrint: pip install 'seryvon[pdf]'",
        ) from exc
    filename = f"seryvon-{report.domain}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


async def _validate_key(connector: str, value: str) -> None:
    """Live-probe a BYOK key before storing it. Raises HTTPException(422) on failure.

    Uses the cheapest possible test call for each connector: no side effects,
    no LLM tokens consumed (auth-only endpoints where available).
    """
    import httpx

    if connector == "dataforseo":
        from seryvon.connectors.dataforseo import _dataforseo_credentials

        creds = _dataforseo_credentials(value)
        if creds is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "DataForSEO key must be 'login:password'"
                    " or a base64 token from the DataForSEO dashboard"
                ),
            )
        # Auth-only probe: GET /v3/merchant/google/locations — returns 200 on valid
        # credentials regardless of plan; 401/403 on bad credentials.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://api.dataforseo.com/v3/appendix/user_data",
                    headers={"Authorization": f"Basic {creds}"},
                )
            if r.status_code in (401, 403):
                raise HTTPException(
                    status_code=422,
                    detail="DataForSEO: authentication failed — check credentials",
                )
            if r.status_code not in (200, 429):
                raise HTTPException(
                    status_code=422,
                    detail=f"DataForSEO: unexpected response {r.status_code}",
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=422, detail=f"DataForSEO: network error — {exc}"
            ) from exc

    elif connector == "psi":
        # Auth-only probe: a minimal PSI request that resolves in < 3 s and
        # costs no Lighthouse quota. A 400 (bad request) still proves the key
        # was accepted; a 403 means the key is invalid or the API is disabled.
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                    params={"url": "https://www.google.com", "key": value, "strategy": "desktop"},
                )
            if r.status_code == 403:
                raise HTTPException(
                    status_code=422,
                    detail="PSI: key rejected by Google API — verify on console.cloud.google.com",
                )
            if r.status_code not in (200, 400, 429):
                raise HTTPException(
                    status_code=422, detail=f"PSI: unexpected response {r.status_code}"
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=422, detail=f"PSI: network error — {exc}") from exc

    elif connector == "opr":
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    "https://openpagerank.com/api/v1.0/getPageRank",
                    params={"domains[]": "google.com"},
                    headers={"API-OPR": value},
                )
            if r.status_code == 401:
                raise HTTPException(status_code=422, detail="OPR: invalid API key")
            if r.status_code not in (200, 429):
                raise HTTPException(
                    status_code=422, detail=f"OPR: unexpected response {r.status_code}"
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=422, detail=f"OPR: network error — {exc}") from exc

    elif connector == "openai":
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {value}"},
                )
            if r.status_code == 401:
                raise HTTPException(status_code=422, detail="OpenAI: invalid API key")
            if r.status_code not in (200, 429):
                raise HTTPException(
                    status_code=422, detail=f"OpenAI: unexpected response {r.status_code}"
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=422, detail=f"OpenAI: network error — {exc}") from exc

    elif connector == "anthropic":
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": value, "anthropic-version": "2023-06-01"},
                )
            if r.status_code == 401:
                raise HTTPException(status_code=422, detail="Anthropic: invalid API key")
            if r.status_code not in (200, 429):
                raise HTTPException(
                    status_code=422, detail=f"Anthropic: unexpected response {r.status_code}"
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=422, detail=f"Anthropic: network error — {exc}"
            ) from exc

    elif connector == "gemini":
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params={"key": value},
                )
            if r.status_code == 400:
                raise HTTPException(status_code=422, detail="Gemini: invalid API key")
            if r.status_code not in (200, 429):
                raise HTTPException(
                    status_code=422, detail=f"Gemini: unexpected response {r.status_code}"
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=422, detail=f"Gemini: network error — {exc}") from exc

    elif connector == "perplexity":
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    "https://api.perplexity.ai/models",
                    headers={"Authorization": f"Bearer {value}"},
                )
            if r.status_code == 401:
                raise HTTPException(status_code=422, detail="Perplexity: invalid API key")
            if r.status_code not in (200, 404, 429):
                raise HTTPException(
                    status_code=422, detail=f"Perplexity: unexpected response {r.status_code}"
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=422, detail=f"Perplexity: network error — {exc}"
            ) from exc

    elif connector == "serp":
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    "https://serpapi.com/account.json",
                    params={"api_key": value},
                )
            if r.status_code == 401:
                raise HTTPException(status_code=422, detail="SerpAPI: invalid API key")
            if r.status_code not in (200, 429):
                raise HTTPException(
                    status_code=422, detail=f"SerpAPI: unexpected response {r.status_code}"
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=422, detail=f"SerpAPI: network error — {exc}"
            ) from exc

    elif connector == "gsc":
        import json as _json

        try:
            info = _json.loads(value)
        except _json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422, detail="GSC: value must be a valid service account JSON"
            ) from exc
        required = ("type", "client_email", "private_key")
        missing = [k for k in required if not info.get(k)]
        if missing:
            fields = ", ".join(missing)
            raise HTTPException(
                status_code=422,
                detail=f"GSC: missing required fields in service account JSON: {fields}",
            )
        if info.get("type") != "service_account":
            raise HTTPException(
                status_code=422,
                detail='GSC: "type" must be "service_account"',
            )


@app.put("/keys/{connector}", response_model=KeyOut)
async def upsert_key(
    connector: str, body: KeyIn, session: Session = Depends(get_session)
) -> KeyOut:
    """Store or update an encrypted BYOK key. Validates the key live before storing."""
    if connector not in repository.CONNECTOR_FIELD:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector}")
    sk = _encryption_guard()
    value = body.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Key value must not be empty")
    await _validate_key(connector, value)
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
def create_citation_tracking(
    request: CitationRequest,
    response: Response,
) -> CitationTaskOut:
    """Submit LLM citation tracking via Celery IO queue. Poll /citations/tasks/{task_id}."""
    result = run_citation_task.delay(request.domain, request.brand, request.competitors)
    response.headers["Location"] = f"/citations/tasks/{result.id}"
    return CitationTaskOut(task_id=result.id, status_url=f"/citations/tasks/{result.id}")


@app.get("/citations/tasks/{task_id}", response_model=CitationTaskStatus)
def get_citation_task(task_id: str) -> CitationTaskStatus:
    """Poll the status of an async citation-tracking job."""
    return _citation_task_status(task_id)


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
