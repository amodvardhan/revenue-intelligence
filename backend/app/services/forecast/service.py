"""Forecast series and fact_forecast loads."""

from __future__ import annotations

import csv
import io
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, delete, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import FactRevenue, IngestionBatch
from app.models.phase5 import FactForecast, ForecastSeries


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, monthrange(y, m)[1])
    return date(y, m, day)


async def load_forecast_csv(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    file_bytes: bytes,
    label: str,
    scenario: str | None,
    batch_id: uuid.UUID,
) -> tuple[uuid.UUID, int]:
    """Parse CSV: period_start, period_end, amount, currency_code[,business_unit_id,customer_id,external_id]."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Empty CSV")

    norm_map = {h.strip().lower(): h for h in reader.fieldnames if h}
    required = {"period_start", "period_end", "amount", "currency_code"}
    if not required.issubset(set(norm_map.keys())):
        raise ValueError("CSV must have headers: period_start, period_end, amount, currency_code")

    series = ForecastSeries(
        tenant_id=tenant_id,
        label=label,
        scenario=scenario,
        source_mode="imported",
        methodology={"upload": "csv", "created_at": datetime.utcnow().isoformat() + "Z"},
        created_by_user_id=user_id,
    )
    session.add(series)
    await session.flush()

    loaded = 0
    for i, row in enumerate(reader):
        nrow = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        ps = date.fromisoformat(nrow["period_start"])
        pe = date.fromisoformat(nrow["period_end"])
        amt = Decimal(nrow["amount"])
        ccy = nrow["currency_code"].upper()[:3]
        bu = uuid.UUID(nrow["business_unit_id"]) if nrow.get("business_unit_id") else None
        cust = uuid.UUID(nrow["customer_id"]) if nrow.get("customer_id") else None
        ext = (nrow.get("external_id") or f"row-{i}")[:255]
        ff = FactForecast(
            tenant_id=tenant_id,
            forecast_series_id=series.forecast_series_id,
            period_start=ps,
            period_end=pe,
            amount=amt,
            currency_code=ccy,
            org_id=org_id,
            business_unit_id=bu,
            division_id=None,
            customer_id=cust,
            external_id=ext,
            batch_id=batch_id,
        )
        session.add(ff)
        loaded += 1

    await session.flush()
    return series.forecast_series_id, loaded


async def create_statistical_forecast_facts(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    forecast_series_id: uuid.UUID,
    horizon_months: int,
    method: str,
) -> int:
    """Populate fact_forecast from trailing monthly revenue average (simple baseline)."""
    _ = user_id
    fs = await session.get(ForecastSeries, forecast_series_id)
    if fs is None or fs.tenant_id != tenant_id:
        raise LookupError("series not found")
    fs.source_mode = "statistical"

    end_hist = date.today().replace(day=1) - timedelta(days=1)
    start_hist = _add_months(_month_start(end_hist), -11)

    m_stmt = (
        select(
            extract("year", FactRevenue.revenue_date).label("y"),
            extract("month", FactRevenue.revenue_date).label("m"),
            func.coalesce(func.sum(FactRevenue.amount), Decimal("0")).label("tot"),
        )
        .where(
            and_(
                FactRevenue.tenant_id == tenant_id,
                FactRevenue.is_deleted.is_(False),
                FactRevenue.revenue_date >= start_hist,
                FactRevenue.revenue_date <= end_hist,
            )
        )
        .group_by(
            extract("year", FactRevenue.revenue_date),
            extract("month", FactRevenue.revenue_date),
        )
    )
    mres = await session.execute(m_stmt)
    monthly_totals = [row.tot for row in mres.all()]
    if not monthly_totals:
        raise ValueError("no historical revenue for statistical baseline")

    monthly_guess = sum(monthly_totals, Decimal("0")) / Decimal(len(monthly_totals))

    org_row = await session.execute(
        select(FactRevenue.org_id).where(FactRevenue.tenant_id == tenant_id).limit(1)
    )
    org_first = org_row.scalar_one_or_none()
    if org_first is None:
        raise ValueError("no revenue facts to anchor org for statistical forecast")

    ccy_row = await session.execute(
        select(FactRevenue.currency_code).where(FactRevenue.tenant_id == tenant_id).limit(1)
    )
    ccy = str(ccy_row.scalar_one())[:3]

    if method != "trailing_average":
        raise ValueError("unsupported method")

    await session.execute(delete(FactForecast).where(FactForecast.forecast_series_id == forecast_series_id))

    fs.methodology = {
        "method": method,
        "horizon_months": horizon_months,
        "history_from": start_hist.isoformat(),
        "history_to": end_hist.isoformat(),
        "model_family": "trailing_monthly_average",
    }

    start_fc = _month_start(date.today())
    n = 0
    for m in range(horizon_months):
        ps = _add_months(start_fc, m)
        pe = _add_months(ps, 1) - timedelta(days=1)
        ext = f"stat-{ps.isoformat()}"[:255]
        ff = FactForecast(
            tenant_id=tenant_id,
            forecast_series_id=forecast_series_id,
            period_start=ps,
            period_end=pe,
            amount=monthly_guess.quantize(Decimal("0.0001")),
            currency_code=ccy,
            org_id=org_first,
            external_id=ext,
            batch_id=None,
        )
        session.add(ff)
        n += 1
    await session.flush()
    return n
