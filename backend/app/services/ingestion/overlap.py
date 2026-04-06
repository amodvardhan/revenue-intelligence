"""Overlap detection for import scope (tenant + org + period)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import FactRevenue, IngestionBatch


async def scope_has_overlap(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope_org_id: UUID,
    period_start: date,
    period_end: date,
) -> bool:
    """True if completed batches or non-deleted facts overlap the inclusive period for this org."""
    b_stmt = (
        select(IngestionBatch.batch_id)
        .where(
            IngestionBatch.tenant_id == tenant_id,
            IngestionBatch.status == "completed",
            IngestionBatch.scope_org_id == scope_org_id,
            IngestionBatch.period_start.isnot(None),
            IngestionBatch.period_end.isnot(None),
            IngestionBatch.period_start <= period_end,
            IngestionBatch.period_end >= period_start,
        )
        .limit(1)
    )
    b = (await session.execute(b_stmt)).scalar_one_or_none()
    if b is not None:
        return True

    f_stmt = (
        select(FactRevenue.revenue_id)
        .where(
            FactRevenue.tenant_id == tenant_id,
            FactRevenue.org_id == scope_org_id,
            FactRevenue.is_deleted.is_(False),
            FactRevenue.revenue_date >= period_start,
            FactRevenue.revenue_date <= period_end,
        )
        .limit(1)
    )
    f = (await session.execute(f_stmt)).scalar_one_or_none()
    return f is not None


async def soft_delete_facts_in_scope(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    org_id: UUID,
    period_start: date,
    period_end: date,
) -> None:
    """Mark existing facts in scope as deleted (replace flow)."""
    from sqlalchemy import update

    await session.execute(
        update(FactRevenue)
        .where(
            and_(
                FactRevenue.tenant_id == tenant_id,
                FactRevenue.org_id == org_id,
                FactRevenue.is_deleted.is_(False),
                FactRevenue.revenue_date >= period_start,
                FactRevenue.revenue_date <= period_end,
            )
        )
        .values(is_deleted=True)
    )
