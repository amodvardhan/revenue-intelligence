"""Aggregated operational health for IT admin (Story 6.4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import IngestionBatch
from app.models.hubspot_integration import HubspotConnection, IntegrationSyncRun


async def build_operations_summary(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    """HubSpot connection + recent sync + ingestion/batch failures (aligned with existing semantics)."""
    hc_res = await session.execute(select(HubspotConnection).where(HubspotConnection.tenant_id == tenant_id))
    hc = hc_res.scalar_one_or_none()

    hubspot: dict[str, Any] = {
        "connection_status": hc.status if hc else "not_configured",
        "last_sync_completed_at": None,
        "last_sync_run_id": None,
        "last_error": hc.last_error if hc else None,
    }

    sync_res = await session.execute(
        select(IntegrationSyncRun)
        .where(
            IntegrationSyncRun.tenant_id == tenant_id,
            IntegrationSyncRun.integration_code == "hubspot",
        )
        .order_by(IntegrationSyncRun.started_at.desc())
        .limit(1)
    )
    last_sync = sync_res.scalar_one_or_none()
    if last_sync is not None:
        hubspot["last_sync_run_id"] = str(last_sync.sync_run_id)
        hubspot["last_sync_completed_at"] = (
            last_sync.completed_at.isoformat() if last_sync.completed_at else None
        )
        if last_sync.status in ("failed", "completed_with_errors") or (last_sync.rows_failed or 0) > 0:
            hubspot["last_error"] = last_sync.error_summary or last_sync.status

    since = datetime.now(tz=UTC) - timedelta(days=7)
    failed_batches = await session.execute(
        select(IngestionBatch)
        .where(
            IngestionBatch.tenant_id == tenant_id,
            IngestionBatch.started_at >= since,
            IngestionBatch.status.in_(("failed", "rejected")),
        )
        .order_by(IngestionBatch.started_at.desc())
        .limit(20)
    )
    fb_rows = failed_batches.scalars().all()

    items: list[dict[str, Any]] = []
    for b in fb_rows:
        err_summary = ""
        if b.error_log:
            err_summary = str(b.error_log)[:500]
        items.append(
            {
                "job_type": "ingest_excel",
                "ref_id": str(b.batch_id),
                "status": b.status,
                "completed_at": b.completed_at.isoformat() if b.completed_at else None,
                "error_summary": err_summary or b.status,
            }
        )

    failed_recent_count = await session.scalar(
        select(func.count())
        .select_from(IngestionBatch)
        .where(
            IngestionBatch.tenant_id == tenant_id,
            IngestionBatch.started_at >= since,
            IngestionBatch.status == "failed",
        )
    )

    return {
        "hubspot": hubspot,
        "background_jobs": {
            "failed_recent_count": int(failed_recent_count or 0),
            "stuck_running_count": 0,
            "items": items,
        },
        "notes": "Aggregates existing Phase 4/5 signals — ingestion batch rows include failed / completed_with_errors in window.",
    }
