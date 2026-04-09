"""Read-only revenue facts (Phase 1 + Phase 2 drill-down filters and BU scope)."""

from __future__ import annotations

import base64
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.dimensions import DimCustomer
from app.models.facts import FactRevenue
from app.models.tenant import User
from app.schemas.revenue import (
    MatrixLine,
    MatrixMonthColumn,
    RevenueListResponse,
    RevenueMatrixResponse,
    RevenueRow,
)
from app.services.access_scope import accessible_org_ids, business_unit_scope

router = APIRouter(prefix="/revenue", tags=["revenue"])


def _amount_str(d: Decimal) -> str:
    """Serialize money as plain decimal string (no scientific notation)."""
    return format(d, "f")


def _decode_cursor(cursor: str | None) -> int:
    """Opaque cursor carries JSON `{"o": offset}` base64url-encoded."""
    if not cursor:
        return 0
    try:
        pad = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + pad)
        data = json.loads(raw.decode())
        return max(0, int(data.get("o", 0)))
    except (ValueError, json.JSONDecodeError, TypeError):
        return 0


def _encode_cursor(offset: int) -> str | None:
    if offset <= 0:
        return None
    raw = json.dumps({"o": offset}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _month_label(d: date) -> str:
    """Mon-YY label to match workbook / Import preview."""
    return d.strftime("%b-%y")


@router.get(
    "/matrix",
    response_model=RevenueMatrixResponse,
    summary="Customer × month matrix (workbook layout)",
    description="Pivots facts with customers into Sr. No., names, and month columns; "
    "adds a computed MoM delta row per customer (not stored as facts).",
)
async def revenue_customer_matrix(
    org_id: UUID = Query(..., description="Organization scope"),
    revenue_date_from: date | None = Query(None),
    revenue_date_to: date | None = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RevenueMatrixResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You do not have access to this organization",
                    "details": None,
                }
            },
        )

    mode, bu_ids = await business_unit_scope(session, user.user_id)
    restricted = mode == "restricted"

    stmt = (
        select(
            DimCustomer.customer_id,
            DimCustomer.customer_name,
            DimCustomer.customer_name_common,
            FactRevenue.revenue_date,
            func.sum(FactRevenue.amount).label("amt"),
            func.min(FactRevenue.currency_code).label("ccy"),
        )
        .select_from(FactRevenue)
        .join(DimCustomer, DimCustomer.customer_id == FactRevenue.customer_id)
        .where(
            FactRevenue.tenant_id == user.tenant_id,
            FactRevenue.org_id == org_id,
            FactRevenue.is_deleted.is_(False),
            FactRevenue.customer_id.isnot(None),
        )
        .group_by(
            DimCustomer.customer_id,
            DimCustomer.customer_name,
            DimCustomer.customer_name_common,
            FactRevenue.revenue_date,
        )
    )
    if restricted:
        stmt = stmt.where(
            and_(
                FactRevenue.business_unit_id.isnot(None),
                FactRevenue.business_unit_id.in_(bu_ids),
            )
        )
    if revenue_date_from is not None:
        stmt = stmt.where(FactRevenue.revenue_date >= revenue_date_from)
    if revenue_date_to is not None:
        stmt = stmt.where(FactRevenue.revenue_date <= revenue_date_to)

    res = await session.execute(stmt)
    raw_rows = res.all()
    if not raw_rows:
        return RevenueMatrixResponse(
            currency_code="USD",
            month_columns=[],
            lines=[],
            empty_reason="no_customer_facts",
        )

    currency = raw_rows[0][5] or "USD"
    by_customer: dict[UUID, dict] = {}
    month_keys: set[date] = set()

    for cid, cname, ccommon, rev_d, amt, _ccy in raw_rows:
        month_keys.add(rev_d)
        if cid not in by_customer:
            by_customer[cid] = {
                "legal": cname,
                "common": (ccommon or "").strip() or None,
                "amounts": defaultdict(lambda: Decimal("0")),
            }
        by_customer[cid]["amounts"][rev_d] += amt or Decimal("0")

    months_sorted = sorted(month_keys)
    month_columns = [
        MatrixMonthColumn(key=m.isoformat(), label=_month_label(m)) for m in months_sorted
    ]

    lines: list[MatrixLine] = []
    sr = 1
    for cid in sorted(
        by_customer.keys(),
        key=lambda k: (by_customer[k]["legal"] or "").lower(),
    ):
        block = by_customer[cid]
        vals = [block["amounts"].get(m, Decimal("0")) for m in months_sorted]
        lines.append(
            MatrixLine(
                row_type="value",
                sr_no=sr,
                customer_legal=block["legal"],
                customer_common=block["common"],
                amounts=[_amount_str(v) for v in vals],
            )
        )
        delta_amounts: list[str] = []
        for i, v in enumerate(vals):
            if i == 0:
                delta_amounts.append("")
            else:
                delta_amounts.append(_amount_str(v - vals[i - 1]))
        lines.append(
            MatrixLine(
                row_type="delta",
                sr_no=None,
                customer_legal="",
                customer_common=None,
                amounts=delta_amounts,
            )
        )
        sr += 1

    return RevenueMatrixResponse(
        currency_code=currency,
        month_columns=month_columns,
        lines=lines,
        empty_reason=None,
    )


@router.get(
    "",
    response_model=RevenueListResponse,
    summary="List revenue facts",
    description="Tenant-scoped facts filtered by orgs the user may access (user_org_role). "
    "Phase 2: optional BU restriction via user_business_unit_access; drill-down filters. "
    "Amounts are decimal strings. Pagination via limit and opaque cursor.",
)
async def list_revenue(
    org_id: UUID | None = Query(None, description="Filter to this organization"),
    business_unit_id: UUID | None = None,
    division_id: UUID | None = None,
    revenue_type_id: UUID | None = None,
    customer_id: UUID | None = None,
    revenue_date_from: date | None = None,
    revenue_date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RevenueListResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id is not None and org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You do not have access to this organization",
                    "details": None,
                }
            },
        )

    org_scope = {org_id} if org_id is not None else accessible
    if not org_scope:
        return RevenueListResponse(items=[], next_cursor=None)

    mode, bu_ids = await business_unit_scope(session, user.user_id)
    restricted = mode == "restricted"

    offset = _decode_cursor(cursor)
    stmt = (
        select(FactRevenue)
        .where(
            FactRevenue.tenant_id == user.tenant_id,
            FactRevenue.org_id.in_(org_scope),
            FactRevenue.is_deleted.is_(False),
        )
        .order_by(FactRevenue.revenue_date.desc(), FactRevenue.revenue_id.desc())
    )
    if restricted:
        stmt = stmt.where(
            and_(
                FactRevenue.business_unit_id.isnot(None),
                FactRevenue.business_unit_id.in_(bu_ids),
            )
        )
    if business_unit_id is not None:
        stmt = stmt.where(FactRevenue.business_unit_id == business_unit_id)
    if division_id is not None:
        stmt = stmt.where(FactRevenue.division_id == division_id)
    if revenue_type_id is not None:
        stmt = stmt.where(FactRevenue.revenue_type_id == revenue_type_id)
    if customer_id is not None:
        stmt = stmt.where(FactRevenue.customer_id == customer_id)
    if revenue_date_from is not None:
        stmt = stmt.where(FactRevenue.revenue_date >= revenue_date_from)
    if revenue_date_to is not None:
        stmt = stmt.where(FactRevenue.revenue_date <= revenue_date_to)

    fetch = limit + 1
    stmt = stmt.offset(offset).limit(fetch)
    res = await session.execute(stmt)
    rows = list(res.scalars().all())

    has_more = len(rows) > limit
    page = rows[:limit]
    next_c = _encode_cursor(offset + limit) if has_more else None

    items = [
        RevenueRow(
            revenue_id=r.revenue_id,
            amount=_amount_str(r.amount),
            currency_code=r.currency_code,
            revenue_date=r.revenue_date,
            org_id=r.org_id,
            business_unit_id=r.business_unit_id,
            division_id=r.division_id,
            customer_id=r.customer_id,
            revenue_type_id=r.revenue_type_id,
            source_system=r.source_system,
            batch_id=r.batch_id,
        )
        for r in page
    ]
    return RevenueListResponse(items=items, next_cursor=next_c)
