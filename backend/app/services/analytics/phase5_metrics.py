"""Phase 5 — consolidated reporting currency, profitability, forecast vs actual."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimBusinessUnit, DimDivision, DimOrganization, UserOrgRole
from app.models.facts import FactRevenue
from app.models.phase5 import FactCost, FactForecast, ForecastSeries
from app.models.tenant import Tenant
from app.services.access_scope import business_unit_scope
from app.services.analytics.service import Hierarchy, build_revenue_fact_filters
from app.services.fx.service import convert_to_reporting_currency


def _amount_str(d: Decimal) -> str:
    return format(d, "f")


async def _accessible_org_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    res = await session.execute(select(UserOrgRole.org_id).where(UserOrgRole.user_id == user_id))
    return set(res.scalars().all())


def _resolve_org_scope(org_id: uuid.UUID | None, accessible: set[uuid.UUID]) -> set[uuid.UUID]:
    if org_id is not None:
        return {org_id}
    return accessible


async def revenue_consolidated(
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
    reporting_currency_code: str | None,
    include_native_amounts: bool,
) -> tuple[dict, datetime]:
    """Rollup with amounts converted to reporting currency (rate as of revenue_date_to per currency bucket)."""
    mode, bu_ids = await business_unit_scope(session, user_id)
    restricted = mode == "restricted"
    accessible = await _accessible_org_ids(session, user_id)
    org_scope = _resolve_org_scope(org_id, accessible)

    tr = await session.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = tr.scalar_one()
    reporting = (reporting_currency_code or tenant.default_currency_code).upper()

    base_filters = build_revenue_fact_filters(
        tenant_id,
        org_scope,
        restricted,
        bu_ids,
        business_unit_id=business_unit_id,
        division_id=division_id,
        revenue_type_id=revenue_type_id,
        customer_id=customer_id,
    )
    date_filters = [
        FactRevenue.revenue_date >= revenue_date_from,
        FactRevenue.revenue_date <= revenue_date_to,
    ]
    filters = base_filters + date_filters
    as_of = datetime.now(timezone.utc)
    rate_as_of = revenue_date_to

    if hierarchy == "org":
        stmt = (
            select(
                DimOrganization.org_id,
                DimOrganization.org_name,
                FactRevenue.currency_code,
                func.coalesce(func.sum(FactRevenue.amount), Decimal("0")).label("rev"),
            )
            .select_from(DimOrganization)
            .join(FactRevenue, FactRevenue.org_id == DimOrganization.org_id)
            .where(and_(*filters))
            .group_by(DimOrganization.org_id, DimOrganization.org_name, FactRevenue.currency_code)
        )
    elif hierarchy == "bu":
        stmt = (
            select(
                DimOrganization.org_id,
                DimOrganization.org_name,
                DimBusinessUnit.business_unit_id,
                DimBusinessUnit.business_unit_name,
                FactRevenue.currency_code,
                func.coalesce(func.sum(FactRevenue.amount), Decimal("0")).label("rev"),
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
                FactRevenue.currency_code,
            )
        )
    else:
        stmt = (
            select(
                DimOrganization.org_id,
                DimOrganization.org_name,
                DimBusinessUnit.business_unit_id,
                DimBusinessUnit.business_unit_name,
                DimDivision.division_id,
                DimDivision.division_name,
                FactRevenue.currency_code,
                func.coalesce(func.sum(FactRevenue.amount), Decimal("0")).label("rev"),
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
                FactRevenue.currency_code,
            )
        )

    res = await session.execute(stmt)
    rows_raw = res.all()

    # Aggregate per hierarchy row: sum converted reporting + optional native breakdown
    from collections import defaultdict

    key_meta: dict = {}
    reporting_totals: dict[tuple, Decimal] = defaultdict(lambda: Decimal("0"))
    native_parts: dict[tuple, list[dict]] = defaultdict(list)

    for row in rows_raw:
        if hierarchy == "org":
            oid, oname, ccy, rev = row
            key = (str(oid), None, None)
            meta = {
                "org_id": str(oid),
                "org_name": oname,
                "business_unit_id": None,
                "business_unit_name": None,
                "division_id": None,
                "division_name": None,
            }
        elif hierarchy == "bu":
            oid, oname, buid, buname, ccy, rev = row
            key = (str(oid), str(buid), None)
            meta = {
                "org_id": str(oid),
                "org_name": oname,
                "business_unit_id": str(buid),
                "business_unit_name": buname,
                "division_id": None,
                "division_name": None,
            }
        else:
            oid, oname, buid, buname, did, dname, ccy, rev = row
            key = (str(oid), str(buid), str(did))
            meta = {
                "org_id": str(oid),
                "org_name": oname,
                "business_unit_id": str(buid),
                "business_unit_name": buname,
                "division_id": str(did),
                "division_name": dname,
            }
        key_meta[key] = meta
        conv, fx_row, _note = await convert_to_reporting_currency(
            session,
            tenant_id=tenant_id,
            amount=rev or Decimal("0"),
            native_currency_code=ccy,
            reporting_currency_code=reporting,
            as_of_date=rate_as_of,
        )
        reporting_totals[key] += conv
        if include_native_amounts:
            part = {
                "native_amount": _amount_str(rev or Decimal("0")),
                "native_currency_code": ccy,
                "reporting_amount": _amount_str(conv),
                "fx_pair": f"{ccy}/{reporting}",
                "fx_rate_effective_date": fx_row.effective_date.isoformat() if fx_row else rate_as_of.isoformat(),
            }
            native_parts[key].append(part)

    rows_out: list[dict] = []
    for key in sorted(key_meta.keys(), key=lambda k: (k[0], k[1] or "", k[2] or "")):
        meta = key_meta[key]
        rtot = reporting_totals[key]
        out = {
            **meta,
            "revenue": _amount_str(rtot),
            "reporting_currency_code": reporting,
        }
        if include_native_amounts:
            out["native_breakdown"] = native_parts[key]
            out["fx_basis_note"] = f"Rates use pair to {reporting}; effective date ≤ {rate_as_of.isoformat()}."
        rows_out.append(out)

    payload = {
        "hierarchy": hierarchy,
        "revenue_date_from": revenue_date_from.isoformat(),
        "revenue_date_to": revenue_date_to.isoformat(),
        "metric": "actuals",
        "filters": {
            "org_id": str(org_id) if org_id else None,
            "business_unit_id": str(business_unit_id) if business_unit_id else None,
            "division_id": str(division_id) if division_id else None,
            "revenue_type_id": str(revenue_type_id) if revenue_type_id else None,
            "customer_id": str(customer_id) if customer_id else None,
        },
        "rows": rows_out,
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
    }
    return payload, as_of


def _cost_category_filter(cost_scope: str) -> list:
    if cost_scope == "cogs_only":
        return [FactCost.cost_category == "cogs"]
    return []  # fully_loaded: all categories


async def profitability_summary(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    period_start: date,
    period_end: date,
    org_id: uuid.UUID | None,
    business_unit_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
    cost_scope: str,
) -> tuple[dict, datetime]:
    mode, bu_ids = await business_unit_scope(session, user_id)
    restricted = mode == "restricted"
    accessible = await _accessible_org_ids(session, user_id)
    org_scope = _resolve_org_scope(org_id, accessible)

    rev_filters = build_revenue_fact_filters(
        tenant_id,
        org_scope,
        restricted,
        bu_ids,
        business_unit_id=business_unit_id,
        division_id=None,
        revenue_type_id=None,
        customer_id=customer_id,
    ) + [
        FactRevenue.revenue_date >= period_start,
        FactRevenue.revenue_date <= period_end,
    ]

    tr = await session.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = tr.scalar_one()
    reporting = tenant.default_currency_code.upper()

    rev_stmt = select(func.coalesce(func.sum(FactRevenue.amount), Decimal("0"))).where(and_(*rev_filters))
    rev_res = await session.execute(rev_stmt)
    revenue_total = rev_res.scalar_one() or Decimal("0")

    cost_f = [
        FactCost.tenant_id == tenant_id,
        FactCost.org_id.in_(org_scope),
        FactCost.cost_date >= period_start,
        FactCost.cost_date <= period_end,
    ]
    if restricted:
        cost_f.append(
            and_(FactCost.business_unit_id.isnot(None), FactCost.business_unit_id.in_(bu_ids))
        )
    if business_unit_id is not None:
        cost_f.append(FactCost.business_unit_id == business_unit_id)
    if customer_id is not None:
        cost_f.append(FactCost.customer_id == customer_id)
    cost_f.extend(_cost_category_filter(cost_scope))

    cost_stmt = select(func.coalesce(func.sum(FactCost.amount), Decimal("0"))).where(and_(*cost_f))
    cost_res = await session.execute(cost_stmt)
    cost_total = cost_res.scalar_one() or Decimal("0")

    margin = revenue_total - cost_total
    as_of = datetime.now(timezone.utc)
    methodology = (
        "Costs include only category 'cogs'."
        if cost_scope == "cogs_only"
        else "Costs include all uploaded cost categories in scope."
    )
    payload = {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "revenue_total": _amount_str(revenue_total),
        "cost_total": _amount_str(cost_total),
        "margin": _amount_str(margin),
        "currency_code": reporting,
        "cost_scope": cost_scope,
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
        "methodology_note": methodology + " Revenue leg matches analytics rollup filters; see GET /revenue for detail.",
    }
    return payload, as_of


async def forecast_vs_actual(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    forecast_series_id: uuid.UUID,
    period_start: date,
    period_end: date,
    org_id: uuid.UUID | None,
    hierarchy: Hierarchy,
) -> dict:
    fs = await session.get(ForecastSeries, forecast_series_id)
    if fs is None or fs.tenant_id != tenant_id:
        raise LookupError("forecast_series")

    mode, bu_ids = await business_unit_scope(session, user_id)
    restricted = mode == "restricted"
    accessible = await _accessible_org_ids(session, user_id)
    org_scope = _resolve_org_scope(org_id, accessible)

    fact_filters = build_revenue_fact_filters(
        tenant_id,
        org_scope,
        restricted,
        bu_ids,
        business_unit_id=None,
        division_id=None,
        revenue_type_id=None,
        customer_id=None,
    ) + [
        FactRevenue.revenue_date >= period_start,
        FactRevenue.revenue_date <= period_end,
    ]

    rev_stmt = select(func.coalesce(func.sum(FactRevenue.amount), Decimal("0"))).where(and_(*fact_filters))
    rev_sum = (await session.execute(rev_stmt)).scalar_one() or Decimal("0")

    ff = [
        FactForecast.forecast_series_id == forecast_series_id,
        FactForecast.period_start >= period_start,
        FactForecast.period_end <= period_end,
    ]
    if org_id:
        ff.append(FactForecast.org_id == org_id)

    fc_stmt = select(func.coalesce(func.sum(FactForecast.amount), Decimal("0"))).where(and_(*ff))
    fc_sum = (await session.execute(fc_stmt)).scalar_one() or Decimal("0")

    return {
        "forecast_series_id": str(forecast_series_id),
        "forecast_label": fs.label,
        "source_mode": fs.source_mode,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "hierarchy": hierarchy,
        "series_actual": {
            "metric": "booked_actuals",
            "total": _amount_str(rev_sum),
            "note": "Sum of fact_revenue in scope for the period (native currency amounts; not FX-adjusted here).",
        },
        "series_forecast": {
            "metric": "forecast",
            "total": _amount_str(fc_sum),
            "note": "Sum of fact_forecast for this series and period window.",
        },
        "period_boundary_note": "Actuals use revenue_date; forecast uses period_start/period_end buckets — align grain in uploads.",
    }
