# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Celery application and queue routing.

Per document 03, §6, two distinct queues:
- `cpu`: crawl, rendering, scoring, static ASO;
- `io` : LLM/SERP calls (IO-bound).

A worker blocked on an LLM call must not monopolize a CPU core.
In Phase 0, a single demo task (`run_audit_task`) is exposed.
"""

from __future__ import annotations

from celery import Celery

from seryvon.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "seryvon",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["seryvon.tasks.audit", "seryvon.tasks.citation"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_default_queue="cpu",
    task_routes={
        "seryvon.tasks.audit.*": {"queue": "cpu"},
        "seryvon.tasks.io.*": {"queue": "io"},
    },
    task_track_started=True,
    worker_hijack_root_logger=False,
)
