"""Segment rules and membership materialization."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimCustomer
from app.models.facts import FactRevenue
from app.models.phase5 import SegmentDefinition, SegmentMembership


async def materialize_segment_membership(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    segment_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> int:
    """Evaluate rule_definition and persist membership for the period window."""
    seg = await session.get(SegmentDefinition, segment_id)
    if seg is None or seg.tenant_id != tenant_id:
        raise LookupError("segment not found")

    rule = seg.rule_definition
    rtype = rule.get("type")
    customer_ids: list[uuid.UUID] = []

    if rtype == "customers_in_org":
        oid = uuid.UUID(rule["org_id"])
        res = await session.execute(
            select(DimCustomer.customer_id).where(
                and_(DimCustomer.tenant_id == tenant_id, DimCustomer.org_id == oid)
            )
        )
        customer_ids = [r[0] for r in res.all()]
    elif rtype == "customers_with_revenue":
        oid = uuid.UUID(rule["org_id"])
        rf = date.fromisoformat(rule["revenue_date_from"])
        rt = date.fromisoformat(rule["revenue_date_to"])
        from decimal import Decimal as D

        min_total = rule.get("min_total")
        min_dec = D(min_total) if min_total is not None else D("0")
        stmt = (
            select(FactRevenue.customer_id, func.coalesce(func.sum(FactRevenue.amount), 0))
            .where(
                and_(
                    FactRevenue.tenant_id == tenant_id,
                    FactRevenue.is_deleted.is_(False),
                    FactRevenue.org_id == oid,
                    FactRevenue.revenue_date >= rf,
                    FactRevenue.revenue_date <= rt,
                    FactRevenue.customer_id.isnot(None),
                )
            )
            .group_by(FactRevenue.customer_id)
            .having(func.coalesce(func.sum(FactRevenue.amount), 0) >= min_dec)
        )
        res = await session.execute(stmt)
        customer_ids = [row[0] for row in res.all() if row[0] is not None]
    else:
        raise ValueError("SEGMENT_RULE_INVALID")

    await session.execute(
        delete(SegmentMembership).where(
            and_(
                SegmentMembership.segment_id == segment_id,
                SegmentMembership.segment_version == seg.version,
                SegmentMembership.period_start == period_start,
                SegmentMembership.period_end == period_end,
            )
        )
    )

    n = 0
    for cid in customer_ids:
        sm = SegmentMembership(
            tenant_id=tenant_id,
            segment_id=segment_id,
            segment_version=seg.version,
            customer_id=cid,
            period_start=period_start,
            period_end=period_end,
            as_of_date=None,
        )
        session.add(sm)
        n += 1
    await session.flush()
    return n
