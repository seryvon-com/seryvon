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

import uuid
from collections.abc import Iterator
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, HttpUrl
from sqlalchemy.orm import Session

from seryvon import __version__
from seryvon.core.audit import run_audit
from seryvon.core.config import AuditConfig
from seryvon.db import repository
from seryvon.db.base import session_scope
from seryvon.models.report import AuditReport

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


class AuditSummaryOut(BaseModel):
    """Audit summary for the history."""

    model_config = ConfigDict(from_attributes=True)

    audit_id: uuid.UUID
    domain: str
    score_global: float | None
    started_at: datetime


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}


@app.post("/audits", response_model=AuditReport)
async def create_audit(
    request: AuditRequest, response: Response, session: Session = Depends(get_session)
) -> AuditReport:
    """Run an audit (synchronous), persist it and return the full report."""
    report = await run_audit(str(request.url), AuditConfig.default())
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


@app.get("/audits", response_model=list[AuditSummaryOut])
def list_audits(
    domain: str, session: Session = Depends(get_session)
) -> list[repository.AuditSummary]:
    """Audit history of a domain (most recent first)."""
    return repository.list_audits(session, domain)
