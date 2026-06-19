"""Asynchronous orchestration (Celery)."""

from seryvon.tasks.app import celery_app

__all__ = ["celery_app"]
