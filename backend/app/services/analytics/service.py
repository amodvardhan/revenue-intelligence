"""Rollup and period-over-period comparison from fact_revenue (canonical truth)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimBusinessUnit, DimDivision, DimOrganization
from app.models.dimensions import UserOrgRole
from app.models.facts import FactRevenue
from app.services.access_scope import business_unit_scope

Hierarchy = Literal["org", "bu", "division"]
CompareKind = Literal["mom", "qoq", "yoy"]


def _amount_str(d: Decimal) -> str:
    return format(d, "f")


def _pct_str(num: Decimal, den: Decimal) -> str:
    if den == 0:
        return "0.0000"
    return format((num / den).quantize(Decimal("0.0001")), "f")


async def _accessible_org_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    res = await session.execute(select(UserOrgRole.org_id).where(UserOrgRole.user_id == user_id))
    return set(res.scalars().all())


def _resolve_org_scope(org_id: uuid.UUID | None, accessible: set[uuid.UUID]) -> set[uuid.UUID]:
    if org_id is not None:
        return {org_id}
    return accessible


def build_revenue_fact_filters(
    tenant_id: uuid.UUID,
    org_scope: set[uuid.UUID],
    restricted: bool,
    bu_ids: list[uuid.UUID],
    *,
    business_unit_id: uuid.UUID | None,
    division_id: uuid.UUID | None,
    revenue_type_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
) -> list:
    f: list = [
        FactRevenue.tenant_id == tenant_id,
        FactRevenue.is_deleted.is_(False),
        FactRevenue.org_id.in_(org_scope),
    ]
    if restricted:
        f.append(
            and_(
                FactRevenue.business_unit_id.isnot(None),
                FactRevenue.business_unit_id.in_(bu_ids),
            )
        )
    if business_unit_id is not None:
        f.append(FactRevenue.business_unit_id == business_unit_id)
    if division_id is not None:
        f.append(FactRevenue.division_id == division_id)
    if revenue_type_id is not None:
        f.append(FactRevenue.revenue_type_id == revenue_type_id)
    if customer_id is not None:
        f.append(FactRevenue.customer_id == customer_id)
    return f


async def revenue_rollup(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    hierarchy: Hierarchy,
    revenue_date_from: date,
    revenue_date_to: date,
    org_id: uuid.UUID | None,
    business_unit_id: uuid.UUID | None,
    division_id: uuid.UUID | None,
    revenue_type_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
) -> tuple[dict, datetime]:
    mode, bu_ids = await business_unit_scope(session, user_id)
    restricted = mode == "restricted"
    accessible = await _accessible_org_ids(session, user_id)
    org_scope = _resolve_org_scope(org_id, accessible)

    date_filters = [
        FactRevenue.revenue_date >= revenue_date_from,
        FactRevenue.revenue_date <= revenue_date_to,
    ]
    base = build_revenue_fact_filters(
        tenant_id,
        org_scope,
        restricted,
        bu_ids,
        business_unit_id=business_unit_id,
        division_id=division_id,
        revenue_type_id=revenue_type_id,
        customer_id=customer_id,
    )
    filters = base + date_filters
    as_of = datetime.now(timezone.utc)

    if hierarchy == "org":
        rows = await _rollup_org(session, filters)
    elif hierarchy == "bu":
        rows = await _rollup_bu(session, filters)
    else:
        rows = await _rollup_division(session, filters)

    payload = {
        "hierarchy": hierarchy,
        "revenue_date_from": revenue_date_from.isoformat(),
        "revenue_date_to": revenue_date_to.isoformat(),
        "filters": {
            "org_id": str(org_id) if org_id else None,
            "business_unit_id": str(business_unit_id) if business_unit_id else None,
            "division_id": str(division_id) if division_id else None,
            "revenue_type_id": str(revenue_type_id) if revenue_type_id else None,
            "customer_id": str(customer_id) if customer_id else None,
        },
        "rows": rows,
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
    }
    return payload, as_of


async def _rollup_org(session: AsyncSession, filters: list) -> list[dict]:
    stmt = (
        select(
            DimOrganization.org_id,
            DimOrganization.org_name,
            func.coalesce(func.sum(FactRevenue.amount), Decimal("0")).label("revenue"),
            func.count(func.distinct(FactRevenue.business_unit_id)).label("child_count"),
        )
        .select_from(DimOrganization)
        .join(FactRevenue, FactRevenue.org_id == DimOrganization.org_id)
        .where(and_(*filters))
        .group_by(DimOrganization.org_id, DimOrganization.org_name)
    )
    res = await session.execute(stmt)
    rows_out: list[dict] = []
    for oid, oname, revenue, cc in res.all():
        rows_out.append(
            {
                "org_id": str(oid),
                "org_name": oname,
                "business_unit_id": None,
                "business_unit_name": None,
                "division_id": None,
                "division_name": None,
                "revenue": _amount_str(revenue),
                "child_count": int(cc or 0),
            }
        )
    return rows_out


async def _rollup_bu(session: AsyncSession, filters: list) -> list[dict]:
    stmt = (
        select(
            DimOrganization.org_id,
            DimOrganization.org_name,
            DimBusinessUnit.business_unit_id,
            DimBusinessUnit.business_unit_name,
            func.coalesce(func.sum(FactRevenue.amount), Decimal("0")).label("revenue"),
            func.count(func.distinct(FactRevenue.division_id)).label("child_count"),
        )
        .select_from(FactRevenue)
        .join(DimOrganization, DimOrganization.org_id == FactRevenue.org_id)
        .join(DimBusinessUnit, DimBusinessUnit.business_unit_id == FactRevenue.business_unit_id)
        .where(and_(*filters, FactRevenue.business_unit_id.isnot(None)))
        .group_by(
            DimOrganization.org_id,
            DimOrganization.org_name,
            DimBusinessUnit.business_unit_id,
            DimBusinessUnit.business_unit_name,
        )
    )
    res = await session.execute(stmt)
    rows_out: list[dict] = []
    for oid, oname, buid, buname, revenue, cc in res.all():
        rows_out.append(
            {
                "org_id": str(oid),
                "org_name": oname,
                "business_unit_id": str(buid),
                "business_unit_name": buname,
                "division_id": None,
                "division_name": None,
                "revenue": _amount_str(revenue),
                "child_count": int(cc or 0),
            }
        )
    return rows_out


async def _rollup_division(session: AsyncSession, filters: list) -> list[dict]:
    stmt = (
        select(
            DimOrganization.org_id,
            DimOrganization.org_name,
            DimBusinessUnit.business_unit_id,
            DimBusinessUnit.business_unit_name,
            DimDivision.division_id,
            DimDivision.division_name,
            func.coalesce(func.sum(FactRevenue.amount), Decimal("0")).label("revenue"),
        )
        .select_from(FactRevenue)
        .join(DimOrganization, DimOrganization.org_id == FactRevenue.org_id)
        .join(DimBusinessUnit, DimBusinessUnit.business_unit_id == FactRevenue.business_unit_id)
        .join(DimDivision, DimDivision.division_id == FactRevenue.division_id)
        .where(and_(*filters, FactRevenue.division_id.isnot(None)))
        .group_by(
            DimOrganization.org_id,
            DimOrganization.org_name,
            DimBusinessUnit.business_unit_id,
            DimBusinessUnit.business_unit_name,
            DimDivision.division_id,
            DimDivision.division_name,
        )
    )
    res = await session.execute(stmt)
    rows_out: list[dict] = []
    for oid, oname, buid, buname, did, dname, revenue in res.all():
        rows_out.append(
            {
                "org_id": str(oid),
                "org_name": oname,
                "business_unit_id": str(buid),
                "business_unit_name": buname,
                "division_id": str(did),
                "division_name": dname,
                "revenue": _amount_str(revenue),
                "child_count": 0,
            }
        )
    return rows_out


async def revenue_compare(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    hierarchy: Hierarchy,
    compare: CompareKind,
    current_period_from: date,
    current_period_to: date,
    comparison_period_from: date,
    comparison_period_to: date,
    org_id: uuid.UUID | None,
    business_unit_id: uuid.UUID | None,
    division_id: uuid.UUID | None,
    revenue_type_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
) -> tuple[dict, datetime]:
    mode, bu_ids = await business_unit_scope(session, user_id)
    restricted = mode == "restricted"
    accessible = await _accessible_org_ids(session, user_id)
    org_scope = _resolve_org_scope(org_id, accessible)

    base = build_revenue_fact_filters(
        tenant_id,
        org_scope,
        restricted,
        bu_ids,
        business_unit_id=business_unit_id,
        division_id=division_id,
        revenue_type_id=revenue_type_id,
        customer_id=customer_id,
    )

    cur_filters = base + [
        FactRevenue.revenue_date >= current_period_from,
        FactRevenue.revenue_date <= current_period_to,
    ]
    cmp_filters = base + [
        FactRevenue.revenue_date >= comparison_period_from,
        FactRevenue.revenue_date <= comparison_period_to,
    ]

    as_of = datetime.now(timezone.utc)
    cur_keyed = await _sum_by_hierarchy(session, hierarchy, cur_filters)
    cmp_keyed = await _sum_by_hierarchy(session, hierarchy, cmp_filters)

    all_keys = set(cur_keyed) | set(cmp_keyed)
    rows_out: list[dict] = []

    def _sort_key(k: tuple[str | None, str | None, str | None]) -> tuple:
        return (k[0] or "", k[1] or "", k[2] or "")

    for key in sorted(all_keys, key=_sort_key):
        cur_t = cur_keyed.get(key)
        cmp_t = cmp_keyed.get(key)
        cur_amt, cur_miss, cur_meta = cur_t if cur_t else (Decimal("0"), True, {})
        cmp_amt, cmp_miss, cmp_meta = cmp_t if cmp_t else (Decimal("0"), True, {})
        meta = {**cmp_meta, **cur_meta}
        abs_ch = cur_amt - cmp_amt
        if cur_miss or cmp_miss:
            pct: str | None = None
        elif cmp_amt == 0:
            pct = "0.0000" if cur_amt == 0 else None
        else:
            pct = _pct_str(abs_ch, cmp_amt)
        rows_out.append(
            {
                **meta,
                "current_revenue": None if cur_miss else _amount_str(cur_amt),
                "comparison_revenue": None if cmp_miss else _amount_str(cmp_amt),
                "absolute_change": _amount_str(abs_ch),
                "percent_change": pct,
                "current_missing": cur_miss,
                "comparison_missing": cmp_miss,
            }
        )

    payload = {
        "hierarchy": hierarchy,
        "compare": compare,
        "current_period": {
            "from": current_period_from.isoformat(),
            "to": current_period_to.isoformat(),
            "label": _period_label(current_period_from, current_period_to, compare),
        },
        "comparison_period": {
            "from": comparison_period_from.isoformat(),
            "to": comparison_period_to.isoformat(),
            "label": _period_label(comparison_period_from, comparison_period_to, compare),
        },
        "rows": rows_out,
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
    }
    return payload, as_of


def _period_label(d0: date, d1: date, compare: CompareKind) -> str:
    _ = compare
    return f"{d0.isoformat()} – {d1.isoformat()}"


async def _sum_by_hierarchy(
    session: AsyncSession,
    hierarchy: Hierarchy,
    filters: list,
) -> dict[tuple[str | None, str | None, str | None], tuple[Decimal, bool, dict]]:
    """Key (org_id, bu_id, div_id) str or None — matches hierarchy grain."""

    if hierarchy == "org":
        stmt = (
            select(
                DimOrganization.org_id,
                DimOrganization.org_name,
                func.coalesce(func.sum(FactRevenue.amount), Decimal("0")),
            )
            .select_from(DimOrganization)
            .join(FactRevenue, FactRevenue.org_id == DimOrganization.org_id)
            .where(and_(*filters))
            .group_by(DimOrganization.org_id, DimOrganization.org_name)
        )
        res = await session.execute(stmt)
        out: dict[tuple[str | None, str | None, str | None], tuple[Decimal, bool, dict]] = {}
        for oid, oname, total in res.all():
            key = (str(oid), None, None)
            out[key] = (
                total or Decimal("0"),
                False,
                {
                    "org_id": str(oid),
                    "org_name": oname,
                    "business_unit_id": None,
                    "business_unit_name": None,
                    "division_id": None,
                    "division_name": None,
                },
            )
        return out

    if hierarchy == "bu":
        stmt = (
            select(
                DimBusinessUnit.business_unit_id,
                DimBusinessUnit.business_unit_name,
                func.coalesce(func.sum(FactRevenue.amount), Decimal("0")),
            )
            .select_from(FactRevenue)
            .join(DimBusinessUnit, DimBusinessUnit.business_unit_id == FactRevenue.business_unit_id)
            .where(and_(*filters, FactRevenue.business_unit_id.isnot(None)))
            .group_by(DimBusinessUnit.business_unit_id, DimBusinessUnit.business_unit_name)
        )
        res = await session.execute(stmt)
        out = {}
        for buid, buname, total in res.all():
            key = (None, str(buid), None)
            out[key] = (
                total or Decimal("0"),
                False,
                {
                    "business_unit_id": str(buid),
                    "business_unit_name": buname,
                },
            )
        return out

    stmt = (
        select(
            DimDivision.division_id,
            DimDivision.division_name,
            func.coalesce(func.sum(FactRevenue.amount), Decimal("0")),
        )
        .select_from(FactRevenue)
        .join(DimDivision, DimDivision.division_id == FactRevenue.division_id)
        .where(and_(*filters, FactRevenue.division_id.isnot(None)))
        .group_by(DimDivision.division_id, DimDivision.division_name)
    )
    res = await session.execute(stmt)
    out = {}
    for did, dname, total in res.all():
        key = (None, None, str(did))
        out[key] = (
            total or Decimal("0"),
            False,
            {
                "division_id": str(did),
                "division_name": dname,
            },
        )
    return out

