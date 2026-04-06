"""Celery application instance."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "revenue_intelligence",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
)

import app.tasks.ingest_tasks  # noqa: E402, F401 — register Celery tasks
import app.tasks.sync_tasks  # noqa: E402, F401 — HubSpot sync

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=29 * 60,
    task_autoretry_for=(ConnectionError, OSError),
    task_retry_kwargs={"max_retries": 3, "countdown": 60},
)
