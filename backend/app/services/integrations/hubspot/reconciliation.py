"""Excel vs HubSpot reconciliation and conflict rows."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import FactRevenue
from app.models.hubspot_integration import RevenueSourceConflict
from app.services.access_scope import accessible_org_ids


def _month_bounds(month_start: date) -> tuple[date, date]:
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    last_day = next_month - timedelta(days=1)
    return month_start, last_day


def reconciliation_key(
    tenant_id: uuid.UUID,
    org_id: uuid.UUID,
    customer_id: uuid.UUID | None,
    month_start: date,
) -> str:
    cid = str(customer_id) if customer_id else "none"
    return f"{tenant_id}:{org_id}:{cid}:{month_start.isoformat()}"


async def detect_revenue_conflicts(session: AsyncSession, *, tenant_id: uuid.UUID) -> int:
    """Insert or update open conflict rows when monthly excel and hubspot totals differ."""
    q = text(
        """
        WITH excel AS (
            SELECT org_id, customer_id,
                   date_trunc('month', revenue_date)::date AS m,
                   SUM(amount) AS amt
            FROM fact_revenue
            WHERE tenant_id = CAST(:tid AS uuid)
              AND is_deleted = false
              AND source_system = 'excel'
            GROUP BY org_id, customer_id, date_trunc('month', revenue_date)
        ),
        hs AS (
            SELECT org_id, customer_id,
                   date_trunc('month', revenue_date)::date AS m,
                   SUM(amount) AS amt
            FROM fact_revenue
            WHERE tenant_id = CAST(:tid AS uuid)
              AND is_deleted = false
              AND source_system = 'hubspot'
            GROUP BY org_id, customer_id, date_trunc('month', revenue_date)
        )
        SELECT e.org_id, e.customer_id, e.m, e.amt AS excel_amt, h.amt AS hs_amt
        FROM excel e
        INNER JOIN hs h
          ON e.org_id = h.org_id
         AND e.m = h.m
         AND (e.customer_id = h.customer_id
              OR (e.customer_id IS NULL AND h.customer_id IS NULL))
        WHERE e.amt IS DISTINCT FROM h.amt
        """
    )
    res = await session.execute(q, {"tid": str(tenant_id)})
    rows = res.mappings().all()
    now = datetime.now(tz=timezone.utc)
    n = 0
    for row in rows:
        org_id = row["org_id"]
        customer_id = row["customer_id"]
        m = row["m"]
        if isinstance(m, datetime):
            m = m.date()
        month_start = date(m.year, m.month, 1)
        ps, pe = _month_bounds(month_start)
        rkey = reconciliation_key(tenant_id, org_id, customer_id, month_start)
        existing = await session.execute(
            select(RevenueSourceConflict).where(
                RevenueSourceConflict.tenant_id == tenant_id,
                RevenueSourceConflict.reconciliation_key == rkey,
            )
        )
        ex = existing.scalar_one_or_none()
        if ex is None:
            session.add(
                RevenueSourceConflict(
                    tenant_id=tenant_id,
                    reconciliation_key=rkey,
                    customer_id=customer_id,
                    period_start=ps,
                    period_end=pe,
                    excel_amount=row["excel_amt"],
                    hubspot_amount=row["hs_amt"],
                    status="open",
                    detected_at=now,
                    updated_at=now,
                )
            )
            n += 1
        elif ex.status == "open":
            ex.excel_amount = row["excel_amt"]
            ex.hubspot_amount = row["hs_amt"]
            ex.updated_at = now
            n += 1
    await session.flush()
    return n


async def source_reconciliation_report(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    revenue_date_from: date,
    revenue_date_to: date,
    org_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
    grain: str,
) -> dict[str, Any]:
    """Aggregates for GET /analytics/revenue/source-reconciliation."""
    orgs = await accessible_org_ids(session, user_id)
    if not orgs:
        return {
            "revenue_date_from": revenue_date_from.isoformat(),
            "revenue_date_to": revenue_date_to.isoformat(),
            "rows": [],
            "as_of": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    org_scope = {org_id} if org_id is not None else orgs
    if org_id is not None and org_id not in orgs:
        return {
            "revenue_date_from": revenue_date_from.isoformat(),
            "revenue_date_to": revenue_date_to.isoformat(),
            "rows": [],
            "as_of": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    org_scope = org_scope & orgs
    if not org_scope:
        return {
            "revenue_date_from": revenue_date_from.isoformat(),
            "revenue_date_to": revenue_date_to.isoformat(),
            "rows": [],
            "as_of": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    excel_amt = func.coalesce(
        func.sum(FactRevenue.amount).filter(FactRevenue.source_system == "excel"),
        0,
    )
    hs_amt = func.coalesce(
        func.sum(FactRevenue.amount).filter(FactRevenue.source_system == "hubspot"),
        0,
    )

    filters = [
        FactRevenue.tenant_id == tenant_id,
        FactRevenue.is_deleted.is_(False),
        FactRevenue.revenue_date >= revenue_date_from,
        FactRevenue.revenue_date <= revenue_date_to,
        FactRevenue.org_id.in_(org_scope),
    ]
    if customer_id is not None:
        filters.append(FactRevenue.customer_id == customer_id)

    if grain == "month":
        period = func.date_trunc("month", FactRevenue.revenue_date)
        stmt = (
            select(
                FactRevenue.org_id,
                FactRevenue.customer_id,
                period.label("period"),
                excel_amt.label("excel_total"),
                hs_amt.label("hubspot_total"),
            )
            .where(and_(*filters))
            .group_by(FactRevenue.org_id, FactRevenue.customer_id, period)
        )
    elif grain == "customer":
        stmt = (
            select(
                FactRevenue.org_id,
                FactRevenue.customer_id,
                excel_amt.label("excel_total"),
                hs_amt.label("hubspot_total"),
            )
            .where(and_(*filters))
            .group_by(FactRevenue.org_id, FactRevenue.customer_id)
        )
    else:
        stmt = (
            select(
                FactRevenue.org_id,
                excel_amt.label("excel_total"),
                hs_amt.label("hubspot_total"),
            )
            .where(and_(*filters))
            .group_by(FactRevenue.org_id)
        )

    res = await session.execute(stmt)
    raw_rows = res.mappings().all()
    rows_out: list[dict[str, Any]] = []
    for row in raw_rows:
        ex = Decimal(str(row["excel_total"]))
        hs = Decimal(str(row["hubspot_total"]))
        var = ex - hs
        cc = 1 if ex != hs and ex != 0 and hs != 0 else 0
        item: dict[str, Any] = {
            "org_id": str(row["org_id"]),
            "excel_total": format(ex, "f"),
            "hubspot_total": format(hs, "f"),
            "variance": format(var, "f"),
            "conflict_count": cc,
        }
        if grain != "org":
            cid = row.get("customer_id")
            item["customer_id"] = str(cid) if cid else None
        else:
            item["customer_id"] = None
        rows_out.append(item)

    return {
        "revenue_date_from": revenue_date_from.isoformat(),
        "revenue_date_to": revenue_date_to.isoformat(),
        "rows": rows_out,
        "as_of": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    }
