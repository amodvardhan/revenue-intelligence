"""Celery tasks — HubSpot sync."""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.core.database import apply_session_rls_vars, async_session_factory, set_session_context
from app.services.integrations.hubspot.sync_service import run_hubspot_sync
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="hubspot.run_sync", bind=True)
def run_hubspot_sync_task(self, sync_run_id: str, tenant_id: str, mode: str = "incremental") -> None:
    """Run HubSpot deal sync for a previously created `integration_sync_run` row."""

    async def _run() -> None:
        tid = uuid.UUID(tenant_id)
        sid = uuid.UUID(sync_run_id)
        async with async_session_factory() as session:
            set_session_context(tenant_id=tid, user_id=None)
            await apply_session_rls_vars(session)
            await run_hubspot_sync(session, tenant_id=tid, sync_run_id=sid, mode=mode)
            await session.commit()

    try:
        asyncio.run(_run())
    except Exception:
        logger.exception("HubSpot sync task failed sync_run_id=%s", sync_run_id)
        raise
