"""Celery tasks for async ingestion."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.core.database import async_session_factory, set_session_context
from app.models.facts import IngestionBatch
from app.services.ingestion.ingestion_service import read_uploaded_file, run_ingestion
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ingest.process_batch", bind=True)
def process_ingest_batch(
    self,
    batch_id: str,
    org_id: str,
    scope_org_id: str,
    period_start: str,
    period_end: str,
    replace: bool,
) -> None:
    """Run ingestion pipeline for a pending batch (large file path)."""

    async def _run() -> None:
        oid = UUID(org_id)
        sid = UUID(scope_org_id) if scope_org_id else None
        ps = date.fromisoformat(period_start) if period_start else None
        pe = date.fromisoformat(period_end) if period_end else None
        bid = UUID(batch_id)

        async with async_session_factory() as session:
            res = await session.execute(select(IngestionBatch).where(IngestionBatch.batch_id == bid))
            batch = res.scalar_one_or_none()
            if batch is None:
                logger.error("batch not found: %s", batch_id)
                return
            set_session_context(tenant_id=batch.tenant_id, user_id=batch.initiated_by)
            content = read_uploaded_file(batch.storage_key)
            try:
                await run_ingestion(
                    session,
                    batch_id=bid,
                    file_content=content,
                    org_id=oid,
                    scope_org_id=sid,
                    period_start=ps,
                    period_end=pe,
                    replace=replace,
                )
            except Exception:
                logger.exception("ingest failed batch_id=%s", batch_id)
                raise
            finally:
                if batch.storage_key and batch.storage_key.startswith("file://"):
                    try:
                        Path(batch.storage_key.removeprefix("file://")).unlink(missing_ok=True)
                    except OSError:
                        pass

    asyncio.run(_run())
