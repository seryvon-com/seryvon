# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""API REST (FastAPI).

Phase 0 : `/health` et `/audits` (exécution synchrone d'un audit de home).
L'exécution asynchrone via Celery (job id, statut, persistance) et les endpoints
`/audits/{id}`, `/compare`, `/history` (document 02, §3.2) arrivent en Phase 1+.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl

from seryvon import __version__
from seryvon.core.audit import run_audit
from seryvon.core.config import AuditConfig
from seryvon.models.report import AuditReport

app = FastAPI(
    title="Seryvon API",
    version=__version__,
    summary="Audit déterministe SEO / GEO / GSO / AEO / ASO.",
)


class AuditRequest(BaseModel):
    """Corps de requête pour lancer un audit."""

    url: HttpUrl


@app.get("/health")
def health() -> dict[str, str]:
    """Sonde de disponibilité."""
    return {"status": "ok", "version": __version__}


@app.post("/audits", response_model=AuditReport)
async def create_audit(request: AuditRequest) -> AuditReport:
    """Lance un audit (synchrone en Phase 0) et renvoie le rapport complet."""
    return await run_audit(str(request.url), AuditConfig.default())
