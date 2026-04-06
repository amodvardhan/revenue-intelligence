"""Forecast series and facts (Phase 5)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_phase5_enabled, require_phase5_upload_role
from app.models.phase5 import FactForecast, ForecastSeries
from app.models.tenant import User
from app.services.access_scope import accessible_org_ids
from app.services.forecast.service import create_statistical_forecast_facts

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get(
    "/series",
    summary="List forecast series",
    dependencies=[Depends(require_phase5_enabled)],
)
async def list_forecast_series(
    source_mode: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    limit = min(max(limit, 1), 200)
    stmt = select(ForecastSeries).where(ForecastSeries.tenant_id == user.tenant_id)
    if source_mode in ("imported", "statistical"):
        stmt = stmt.where(ForecastSeries.source_mode == source_mode)
    stmt = stmt.order_by(ForecastSeries.created_at.desc()).limit(limit)
    res = await session.execute(stmt)
    items = []
    for s in res.scalars().all():
        items.append(
            {
                "forecast_series_id": str(s.forecast_series_id),
                "label": s.label,
                "scenario": s.scenario,
                "source_mode": s.source_mode,
                "effective_from": s.effective_from.isoformat() if s.effective_from else None,
                "effective_to": s.effective_to.isoformat() if s.effective_to else None,
                "created_at": s.created_at.isoformat().replace("+00:00", "Z"),
            }
        )
    return {"items": items, "next_cursor": None}


@router.get(
    "/series/{forecast_series_id}",
    summary="Get forecast series detail",
    dependencies=[Depends(require_phase5_enabled)],
)
async def get_forecast_series(
    forecast_series_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    s = await session.get(ForecastSeries, forecast_series_id)
    if s is None or s.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Series not found", "details": None}},
        )
    return {
        "forecast_series_id": str(s.forecast_series_id),
        "label": s.label,
        "scenario": s.scenario,
        "source_mode": s.source_mode,
        "methodology": s.methodology or {},
        "effective_from": s.effective_from.isoformat() if s.effective_from else None,
        "effective_to": s.effective_to.isoformat() if s.effective_to else None,
        "created_at": s.created_at.isoformat().replace("+00:00", "Z"),
    }


@router.get(
    "/facts",
    summary="List forecast facts",
    dependencies=[Depends(require_phase5_enabled)],
)
async def list_forecast_facts(
    forecast_series_id: UUID = Query(...),
    period_start_from: date | None = None,
    period_start_to: date | None = None,
    org_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    customer_id: UUID | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    limit = min(max(limit, 1), 200)
    fs = await session.get(ForecastSeries, forecast_series_id)
    if fs is None or fs.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Series not found", "details": None}},
        )
    acc = await accessible_org_ids(session, user.user_id)
    if org_id is not None and org_id not in acc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Org not accessible", "details": None}},
        )
    f = [
        FactForecast.tenant_id == user.tenant_id,
        FactForecast.forecast_series_id == forecast_series_id,
    ]
    if org_id:
        f.append(FactForecast.org_id == org_id)
    if business_unit_id:
        f.append(FactForecast.business_unit_id == business_unit_id)
    if customer_id:
        f.append(FactForecast.customer_id == customer_id)
    if period_start_from:
        f.append(FactForecast.period_start >= period_start_from)
    if period_start_to:
        f.append(FactForecast.period_start <= period_start_to)
    stmt = select(FactForecast).where(and_(*f)).order_by(FactForecast.period_start).limit(limit)
    res = await session.execute(stmt)
    items = []
    for r in res.scalars().all():
        items.append(
            {
                "forecast_fact_id": str(r.forecast_fact_id),
                "amount": format(r.amount, "f"),
                "currency_code": r.currency_code,
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "org_id": str(r.org_id),
                "business_unit_id": str(r.business_unit_id) if r.business_unit_id else None,
                "customer_id": str(r.customer_id) if r.customer_id else None,
            }
        )
    return {"items": items, "next_cursor": None}


@router.post(
    "/series/{forecast_series_id}/statistical-refresh",
    summary="Refresh statistical forecast facts",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_phase5_enabled)],
)
async def statistical_refresh(
    forecast_series_id: UUID,
    body: dict,
    user: User = Depends(require_phase5_upload_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    horizon = int(body.get("horizon_months", 12))
    method = str(body.get("method", "trailing_average"))
    try:
        n = await create_statistical_forecast_facts(
            session,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            forecast_series_id=forecast_series_id,
            horizon_months=horizon,
            method=method,
        )
        await session.commit()
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Series not found", "details": None}},
        ) from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": None}},
        ) from None
    return {"status": "accepted", "rows_written": n, "source_mode": "statistical"}
