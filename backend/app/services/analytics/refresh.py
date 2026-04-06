"""Refresh materialized analytics and refresh metadata."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import AnalyticsRefreshMetadata

logger = logging.getLogger(__name__)

MV_NAMES = (
    "mv_revenue_monthly_by_org",
    "mv_revenue_monthly_by_bu",
    "mv_revenue_monthly_by_division",
)


async def refresh_analytics_structures(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    batch_id: UUID,
) -> None:
    """Refresh all Phase 2 MVs and upsert analytics_refresh_metadata."""
    completed_at = datetime.now(timezone.utc)
    for name in MV_NAMES:
        try:
            await session.execute(text(f'REFRESH MATERIALIZED VIEW "{name}"'))
        except Exception:
            logger.exception("MV refresh failed tenant=%s structure=%s", tenant_id, name)
            continue
        stmt = insert(AnalyticsRefreshMetadata).values(
            tenant_id=tenant_id,
            structure_name=name,
            last_refresh_completed_at=completed_at,
            last_completed_batch_id=batch_id,
            last_error=None,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_analytics_refresh_tenant_structure",
            set_={
                "last_refresh_completed_at": completed_at,
                "last_completed_batch_id": batch_id,
                "last_error": None,
                "updated_at": completed_at,
            },
        )
        await session.execute(stmt)
    await session.commit()

