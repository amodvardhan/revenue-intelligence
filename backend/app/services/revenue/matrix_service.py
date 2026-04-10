"""Customer × month matrix: aggregate facts, apply manual cell overrides, compute MoM deltas."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import Date, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimCustomer
from app.models.facts import FactRevenue
from app.models.phase7 import RevenueManualCell, RevenueVarianceComment
from app.models.tenant import User
from app.schemas.revenue import MatrixLine, MatrixMonthColumn, RevenueMatrixResponse


def _amount_str(d: Decimal) -> str:
    return format(d, "f")


def _month_label(d: date) -> str:
    return d.strftime("%b-%y")


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


MatrixScope = Literal["organization", "business_unit", "division"]


def _manual_amount(
    manual: dict[tuple[UUID, date, UUID | None, UUID | None], Decimal],
    customer_id: UUID,
    month: date,
    business_unit_id: UUID | None,
    division_id: UUID | None,
) -> Decimal | None:
    """Pick the manual override for the active matrix scope (most specific wins)."""
    m = _month_start(month)
    if division_id is not None and business_unit_id is not None:
        k = (customer_id, m, business_unit_id, division_id)
        if k in manual:
            return manual[k]
        return None
    if business_unit_id is not None:
        k = (customer_id, m, business_unit_id, None)
        if k in manual:
            return manual[k]
        return None
    k0 = (customer_id, m, None, None)
    if k0 in manual:
        return manual[k0]
    return None


def _manual_customer_matches_home_scope(
    home_bu: UUID | None,
    home_div: UUID | None,
    sel_bu: UUID | None,
    sel_div: UUID | None,
) -> bool:
    """Manual rows without fact lines must match the customer's home BU/division when drilling down."""
    if sel_bu is None and sel_div is None:
        return True
    if sel_bu is not None and home_bu is not None and home_bu != sel_bu:
        return False
    if sel_div is not None and home_div is not None and home_div != sel_div:
        return False
    return True


def _scoped_variance_text(
    comment_map: dict[tuple[UUID, date, UUID | None, UUID | None], str],
    customer_id: UUID,
    month: date,
    business_unit_id: UUID | None,
    division_id: UUID | None,
) -> str | None:
    """Resolve variance narrative for matrix scope (most specific wins)."""
    m = _month_start(month)
    if division_id is not None and business_unit_id is not None:
        k = (customer_id, m, business_unit_id, division_id)
        if k in comment_map:
            return comment_map[k]
        return None
    if business_unit_id is not None:
        k = (customer_id, m, business_unit_id, None)
        if k in comment_map:
            return comment_map[k]
        return None
    k0 = (customer_id, m, None, None)
    if k0 in comment_map:
        return comment_map[k0]
    return None


async def build_revenue_matrix(
    session: AsyncSession,
    *,
    user: User,
    org_id: UUID,
    revenue_date_from: date | None,
    revenue_date_to: date | None,
    business_unit_id: UUID | None,
    division_id: UUID | None,
    restricted: bool,
    restricted_bu_ids: set[UUID],
    allow_matrix_full_edit: bool = False,
    dm_editable_customers: set[UUID] | None = None,
) -> RevenueMatrixResponse:
    """Build matrix with optional BU/division scope; manual cells override fact sums for the same scope."""
    dm_set: set[UUID] = dm_editable_customers if dm_editable_customers is not None else set()
    org_wide_matrix = business_unit_id is None and division_id is None
    month_bucket = cast(func.date_trunc("month", FactRevenue.revenue_date), Date)

    stmt = (
        select(
            DimCustomer.customer_id,
            DimCustomer.customer_name,
            DimCustomer.customer_name_common,
            month_bucket.label("month_key"),
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
            month_bucket,
        )
    )
    if restricted:
        stmt = stmt.where(
            and_(
                FactRevenue.business_unit_id.isnot(None),
                FactRevenue.business_unit_id.in_(restricted_bu_ids),
            )
        )
    if business_unit_id is not None:
        stmt = stmt.where(
            or_(
                FactRevenue.business_unit_id == business_unit_id,
                and_(
                    FactRevenue.business_unit_id.is_(None),
                    DimCustomer.business_unit_id == business_unit_id,
                ),
            )
        )
    if division_id is not None:
        stmt = stmt.where(
            or_(
                FactRevenue.division_id == division_id,
                and_(
                    FactRevenue.division_id.is_(None),
                    DimCustomer.division_id == division_id,
                    DimCustomer.business_unit_id == business_unit_id,
                ),
            )
        )
    if revenue_date_from is not None:
        stmt = stmt.where(FactRevenue.revenue_date >= revenue_date_from)
    if revenue_date_to is not None:
        stmt = stmt.where(FactRevenue.revenue_date <= revenue_date_to)

    res = await session.execute(stmt)
    raw_rows = res.all()

    manual_res = await session.execute(
        select(RevenueManualCell).where(
            RevenueManualCell.tenant_id == user.tenant_id,
            RevenueManualCell.org_id == org_id,
        )
    )
    manual_rows = list(manual_res.scalars().all())

    manual_map: dict[tuple[UUID, date, UUID | None, UUID | None], Decimal] = {}
    for m in manual_rows:
        mk = _month_start(m.revenue_month)
        manual_map[(m.customer_id, mk, m.business_unit_id, m.division_id)] = Decimal(m.amount)

    vc_res = await session.execute(
        select(RevenueVarianceComment).where(
            RevenueVarianceComment.tenant_id == user.tenant_id,
            RevenueVarianceComment.org_id == org_id,
        )
    )
    comment_map: dict[tuple[UUID, date, UUID | None, UUID | None], str] = {}
    for vc in vc_res.scalars().all():
        mk = _month_start(vc.revenue_month)
        comment_map[(vc.customer_id, mk, vc.business_unit_id, vc.division_id)] = vc.comment_text

    fact_by_cust_month: dict[UUID, dict[date, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    currency = "USD"

    for cid, _cname, _ccommon, mkey, amt, ccy in raw_rows:
        mk = mkey if isinstance(mkey, date) else date.fromisoformat(str(mkey))
        mk = _month_start(mk)
        fact_by_cust_month[cid][mk] += amt or Decimal("0")
        if ccy:
            currency = ccy

    if manual_rows and not raw_rows:
        currency = manual_rows[0].currency_code or "USD"

    month_keys: set[date] = set()
    for _cid, months in fact_by_cust_month.items():
        month_keys |= set(months.keys())
    for (cid, mk, _bu, _div) in manual_map.keys():
        month_keys.add(_month_start(mk))

    if not month_keys:
        return RevenueMatrixResponse(
            currency_code=currency,
            month_columns=[],
            lines=[],
            empty_reason="no_customer_facts",
            matrix_scope="organization",
        )

    customer_ids: set[UUID] = set(fact_by_cust_month.keys())
    for (cid, _mk, _b, _d) in manual_map.keys():
        customer_ids.add(cid)

    fact_customer_ids = set(fact_by_cust_month.keys())
    only_manual = customer_ids - fact_customer_ids
    if only_manual and (business_unit_id is not None or division_id is not None):
        hres = await session.execute(
            select(DimCustomer.customer_id, DimCustomer.business_unit_id, DimCustomer.division_id).where(
                DimCustomer.customer_id.in_(only_manual),
                DimCustomer.tenant_id == user.tenant_id,
            )
        )
        home_map: dict[UUID, tuple[UUID | None, UUID | None]] = {
            r[0]: (r[1], r[2]) for r in hres.all()
        }
        for cid in list(only_manual):
            bu_h, div_h = home_map.get(cid, (None, None))
            if not _manual_customer_matches_home_scope(bu_h, div_h, business_unit_id, division_id):
                customer_ids.discard(cid)

        month_keys = set()
        for cid in customer_ids:
            month_keys |= set(fact_by_cust_month.get(cid, {}).keys())
        for (cid, mk, _bu, _div) in manual_map.keys():
            if cid in customer_ids:
                month_keys.add(_month_start(mk))
        if not month_keys:
            return RevenueMatrixResponse(
                currency_code=currency,
                month_columns=[],
                lines=[],
                empty_reason="no_customer_facts",
                matrix_scope="organization",
            )

    months_sorted = sorted(month_keys)
    month_columns = [MatrixMonthColumn(key=m.isoformat(), label=_month_label(m)) for m in months_sorted]

    cust_meta: dict[UUID, tuple[str, str | None]] = {}
    for cid, cname, ccommon, _mk, _amt, _ccy in raw_rows:
        if cid not in cust_meta:
            cust_meta[cid] = (cname, (ccommon or "").strip() or None)

    missing = customer_ids - set(cust_meta.keys())
    if missing:
        cres = await session.execute(
            select(DimCustomer.customer_id, DimCustomer.customer_name, DimCustomer.customer_name_common).where(
                DimCustomer.customer_id.in_(missing),
                DimCustomer.tenant_id == user.tenant_id,
            )
        )
        for cid, cname, ccommon in cres.all():
            cust_meta[cid] = (cname, (ccommon or "").strip() or None)

    scope: MatrixScope = "organization"
    if division_id is not None:
        scope = "division"
    elif business_unit_id is not None:
        scope = "business_unit"

    lines: list[MatrixLine] = []
    sr = 1
    for cid in sorted(customer_ids, key=lambda k: (cust_meta.get(k, ("", None))[0] or "").lower()):
        legal, common = cust_meta.get(cid, ("", None))
        vals: list[Decimal] = []
        for m in months_sorted:
            mval = _manual_amount(manual_map, cid, m, business_unit_id, division_id)
            if mval is not None:
                vals.append(mval)
            else:
                vals.append(fact_by_cust_month[cid].get(_month_start(m), Decimal("0")))

        row_editable = allow_matrix_full_edit or (org_wide_matrix and cid in dm_set)
        lines.append(
            MatrixLine(
                row_type="value",
                sr_no=sr,
                customer_id=cid,
                customer_legal=legal,
                customer_common=common,
                amounts=[_amount_str(v) for v in vals],
                amounts_editable=row_editable,
                variance_comments=None,
                variance_comments_editable=False,
            )
        )
        delta_amounts: list[str] = []
        variance_notes: list[str | None] = []
        for i, v in enumerate(vals):
            if i == 0:
                delta_amounts.append("")
                variance_notes.append(None)
            else:
                delta_amounts.append(_amount_str(v - vals[i - 1]))
                m_col = months_sorted[i]
                txt = _scoped_variance_text(comment_map, cid, m_col, business_unit_id, division_id)
                variance_notes.append(txt)
        lines.append(
            MatrixLine(
                row_type="delta",
                sr_no=None,
                customer_id=cid,
                customer_legal="",
                customer_common=None,
                amounts=delta_amounts,
                amounts_editable=False,
                variance_comments=variance_notes,
                variance_comments_editable=row_editable,
            )
        )
        sr += 1

    return RevenueMatrixResponse(
        currency_code=currency,
        month_columns=month_columns,
        lines=lines,
        empty_reason=None,
        matrix_scope=scope,
    )
