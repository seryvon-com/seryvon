# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Audit tasks (CPU-bound queue).

Wraps `run_audit` for Celery execution with full settings resolution (BYOK
keys from DB), persistence, locale, and a hard timeout.

Return value on SUCCESS: ``{"audit_id": "<uuid>"}`` — the API polls this to
redirect the frontend to ``/audits/{audit_id}``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from seryvon.core.audit import run_audit
from seryvon.core.config import AuditConfig
from seryvon.core.settings_resolver import resolve_settings
from seryvon.db import repository
from seryvon.db.base import session_scope
from seryvon.tasks.app import celery_app

log = logging.getLogger(__name__)

_AUDIT_TIMEOUT_SECONDS = 300


@celery_app.task(  # type: ignore[untyped-decorator]
    name="seryvon.tasks.audit.run_audit_task",
    bind=True,
    track_started=True,
    queue="cpu",
)
def run_audit_task(self: Any, url: str, locale: str = "en") -> dict[str, Any]:
    """Run an audit end-to-end and persist the result.

    Celery state transitions: PENDING → STARTED → PROGRESS → SUCCESS | FAILURE.
    PROGRESS meta: ``{"logs": [...], "status": "running"}``.
    On SUCCESS the result dict contains ``audit_id`` (str UUID).
    On FAILURE the exception message is the error.
    """
    log.info("audit_task start url=%s locale=%s task_id=%s", url, locale, self.request.id)

    with session_scope() as session:
        settings = resolve_settings(session)

    config = AuditConfig.default()
    config.locale = locale

    logs: list[str] = []

    def _on_progress(msg: str) -> None:
        logs.append(msg)
        self.update_state(state="PROGRESS", meta={"logs": list(logs), "status": "running"})

    async def _run() -> Any:
        return await asyncio.wait_for(
            run_audit(url, config, settings=settings, on_progress=_on_progress),
            timeout=float(_AUDIT_TIMEOUT_SECONDS),
        )

    report, pages = asyncio.run(_run())

    with session_scope() as session:
        audit_id = repository.persist_report(report, session)
        repository.persist_pages(audit_id, pages, session)

    log.info("audit_task done url=%s audit_id=%s", url, audit_id)
    return {"audit_id": str(audit_id), "logs": logs}
