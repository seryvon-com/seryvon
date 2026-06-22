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

import contextlib
import uuid
from collections.abc import Iterator
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, HttpUrl
from sqlalchemy.orm import Session

from seryvon import __version__
from seryvon.core.audit import run_audit
from seryvon.core.config import AuditConfig, Settings, get_settings
from seryvon.core.crypto import EncryptionError, decrypt_value, encrypt_value, mask_value
from seryvon.db import repository
from seryvon.db.base import session_scope
from seryvon.models.report import AuditReport
from seryvon.scoring import (
    ComparisonMode,
    ComparisonResult,
    IncomparableError,
    compare_scorecards,
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


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}


@app.post("/audits", response_model=AuditReport)
async def create_audit(
    request: AuditRequest, response: Response, session: Session = Depends(get_session)
) -> AuditReport:
    """Run an audit (synchronous), persist it and return the full report."""
    config = AuditConfig.default()
    config.locale = request.locale
    settings = _resolve_settings(session)
    report = await run_audit(str(request.url), config, settings=settings)
    audit_id = repository.persist_report(report, session)
    response.headers["Location"] = f"/audits/{audit_id}"
    return report


@app.get("/audits/{audit_id}", response_model=AuditReport)
def get_audit(audit_id: uuid.UUID, session: Session = Depends(get_session)) -> AuditReport:
    """Reload a persisted audit report (404 if not found)."""
    report = repository.load_report(session, audit_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    return report


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
