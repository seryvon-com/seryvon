# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""API REST (FastAPI).

`/health`, puis le cycle d'audit persisté : `POST /audits` lance et **persiste**
un audit (header `Location: /audits/{id}`), `GET /audits/{id}` relit un rapport,
`GET /audits?domain=…` renvoie l'historique d'un domaine. L'exécution asynchrone
via Celery (statut/polling) arrive en slice B3.
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
    summary="Audit déterministe SEO / GEO / GSO / AEO / ASO.",
)


def get_session() -> Iterator[Session]:
    """Dépendance FastAPI : session transactionnelle par requête."""
    with session_scope() as session:
        yield session


class AuditRequest(BaseModel):
    """Corps de requête pour lancer un audit."""

    url: HttpUrl


class AuditSummaryOut(BaseModel):
    """Résumé d'audit pour l'historique."""

    model_config = ConfigDict(from_attributes=True)

    audit_id: uuid.UUID
    domain: str
    score_global: float | None
    started_at: datetime


@app.get("/health")
def health() -> dict[str, str]:
    """Sonde de disponibilité."""
    return {"status": "ok", "version": __version__}


@app.post("/audits", response_model=AuditReport)
async def create_audit(
    request: AuditRequest, response: Response, session: Session = Depends(get_session)
) -> AuditReport:
    """Lance un audit (synchrone), le persiste et renvoie le rapport complet."""
    report = await run_audit(str(request.url), AuditConfig.default())
    audit_id = repository.persist_report(report, session)
    response.headers["Location"] = f"/audits/{audit_id}"
    return report


@app.get("/audits/{audit_id}", response_model=AuditReport)
def get_audit(audit_id: uuid.UUID, session: Session = Depends(get_session)) -> AuditReport:
    """Relit un rapport d'audit persisté (404 si introuvable)."""
    report = repository.load_report(session, audit_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Audit introuvable")
    return report


@app.get("/audits", response_model=list[AuditSummaryOut])
def list_audits(
    domain: str, session: Session = Depends(get_session)
) -> list[repository.AuditSummary]:
    """Historique des audits d'un domaine (plus récent en premier)."""
    return repository.list_audits(session, domain)
