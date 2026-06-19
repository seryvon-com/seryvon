# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Audit tasks (CPU-bound queue).

Wraps the synchronous `run_audit` orchestrator for execution via Celery.
Persisting the results to the database is wired in Phase 1.
"""

from __future__ import annotations

import asyncio
from typing import Any

from seryvon.core.audit import run_audit
from seryvon.core.config import AuditConfig
from seryvon.tasks.app import celery_app


@celery_app.task(name="seryvon.tasks.audit.run_audit_task")  # type: ignore[untyped-decorator]
def run_audit_task(url: str) -> dict[str, Any]:
    """Run an audit and return the serialized report (dict)."""
    report = asyncio.run(run_audit(url, AuditConfig.default()))
    return report.model_dump(mode="json")
