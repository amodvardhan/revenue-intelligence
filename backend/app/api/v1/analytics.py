"""Phase 2 analytics — rollup, compare, freshness."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_user,
    require_phase5_enabled,
    require_source_reconciliation_role,
)
from app.models.facts import AnalyticsRefreshMetadata
from app.models.tenant import User
from app.services.access_scope import accessible_org_ids
from app.services.analytics.phase5_metrics import (
    forecast_vs_actual,
    profitability_summary,
    revenue_consolidated,
)
from app.services.analytics.service import revenue_compare, revenue_rollup
from app.services.integrations.hubspot.reconciliation import source_reconciliation_report

router = APIRouter(prefix="/analytics", tags=["analytics"])

HIERARCHY_VALUES = ("org", "bu", "division", "customer")
# Phase 5 consolidated / forecast paths remain org | bu | division only.
PHASE5_HIERARCHY_VALUES = ("org", "bu", "division")
COMPARE_VALUES = ("mom", "qoq", "yoy")
GRAIN_VALUES = ("month", "customer", "org")


@router.get(
    "/revenue/rollup",
    summary="Hierarchical revenue rollup",
    description="Story 2.1 / 2.3 — totals by org, BU, or division for an explicit date range.",
)
async def get_revenue_rollup(
    hierarchy: str = Query(..., description="org | bu | division | customer"),
    revenue_date_from: date = Query(...),
    revenue_date_to: date = Query(...),
    org_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    division_id: UUID | None = None,
    revenue_type_id: UUID | None = None,
    customer_id: UUID | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if hierarchy not in HIERARCHY_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"hierarchy must be one of {HIERARCHY_VALUES}",
                    "details": None,
                }
            },
        )
    if revenue_date_to < revenue_date_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "revenue_date_to must be >= revenue_date_from",
                    "details": None,
                }
            },
        )

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

    payload, _as_of = await revenue_rollup(
        session,
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        hierarchy=hierarchy,  # type: ignore[arg-type]
        revenue_date_from=revenue_date_from,
        revenue_date_to=revenue_date_to,
        org_id=org_id,
        business_unit_id=business_unit_id,
        division_id=division_id,
        revenue_type_id=revenue_type_id,
        customer_id=customer_id,
    )
    return payload


@router.get(
    "/revenue/compare",
    summary="Period-over-period revenue comparison",
    description="Story 2.2 — explicit current and comparison windows with labels.",
)
async def get_revenue_compare(
    hierarchy: str = Query(...),
    compare: str = Query(..., description="mom | qoq | yoy"),
    current_period_from: date = Query(...),
    current_period_to: date = Query(...),
    comparison_period_from: date = Query(...),
    comparison_period_to: date = Query(...),
    org_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    division_id: UUID | None = None,
    revenue_type_id: UUID | None = None,
    customer_id: UUID | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if hierarchy not in HIERARCHY_VALUES or compare not in COMPARE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid hierarchy or compare parameter",
                    "details": None,
                }
            },
        )
    if current_period_to < current_period_from or comparison_period_to < comparison_period_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid period range",
                    "details": None,
                }
            },
        )

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

    payload, _as_of = await revenue_compare(
        session,
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        hierarchy=hierarchy,  # type: ignore[arg-type]
        compare=compare,  # type: ignore[arg-type]
        current_period_from=current_period_from,
        current_period_to=current_period_to,
        comparison_period_from=comparison_period_from,
        comparison_period_to=comparison_period_to,
        org_id=org_id,
        business_unit_id=business_unit_id,
        division_id=division_id,
        revenue_type_id=revenue_type_id,
        customer_id=customer_id,
    )
    return payload


@router.get(
    "/revenue/source-reconciliation",
    summary="Excel vs HubSpot revenue comparison",
    description="Phase 4 — aggregates by source_system for Finance reconciliation.",
)
async def get_source_reconciliation(
    revenue_date_from: date = Query(...),
    revenue_date_to: date = Query(...),
    org_id: UUID | None = None,
    customer_id: UUID | None = None,
    grain: str = Query("month", description="month | customer | org"),
    user: User = Depends(require_source_reconciliation_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if grain not in GRAIN_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"grain must be one of {GRAIN_VALUES}",
                    "details": None,
                }
            },
        )
    if revenue_date_to < revenue_date_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "revenue_date_to must be >= revenue_date_from",
                    "details": None,
                }
            },
        )
    return await source_reconciliation_report(
        session,
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        revenue_date_from=revenue_date_from,
        revenue_date_to=revenue_date_to,
        org_id=org_id,
        customer_id=customer_id,
        grain=grain,
    )


@router.get(
    "/freshness",
    summary="Analytics materialization freshness",
    description="Story 2.4 — last refresh times for precomputed structures.",
)
async def get_freshness(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    res = await session.execute(
        select(AnalyticsRefreshMetadata).where(AnalyticsRefreshMetadata.tenant_id == user.tenant_id)
    )
    rows = res.scalars().all()
    structures = []
    for m in rows:
        structures.append(
            {
                "structure_name": m.structure_name,
                "last_refresh_completed_at": m.last_refresh_completed_at.isoformat().replace(
                    "+00:00", "Z"
                )
                if m.last_refresh_completed_at
                else None,
                "last_completed_batch_id": str(m.last_completed_batch_id)
                if m.last_completed_batch_id
                else None,
            }
        )
    return {
        "tenant_id": str(user.tenant_id),
        "structures": structures,
        "notes": (
            "As-of times reflect materialized analytics; row facts via GET /revenue may be newer "
            "until refresh completes."
        ),
    }


@router.get(
    "/revenue/consolidated",
    summary="Revenue rollup in reporting currency",
    description="Phase 5 — actuals converted using fx_rate; optional native breakdown.",
    dependencies=[Depends(require_phase5_enabled)],
)
async def get_revenue_consolidated(
    hierarchy: str = Query(..., description="org | bu | division | customer"),
    revenue_date_from: date = Query(...),
    revenue_date_to: date = Query(...),
    org_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    division_id: UUID | None = None,
    revenue_type_id: UUID | None = None,
    customer_id: UUID | None = None,
    reporting_currency: str | None = None,
    include_native_amounts: bool = False,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if hierarchy not in PHASE5_HIERARCHY_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "consolidated rollup supports org | bu | division only",
                    "details": None,
                }
            },
        )
    if revenue_date_to < revenue_date_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Invalid date range", "details": None}},
        )
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id is not None and org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Org not accessible", "details": None}},
        )
    try:
        payload, _as_of = await revenue_consolidated(
            session,
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            hierarchy=hierarchy,  # type: ignore[arg-type]
            revenue_date_from=revenue_date_from,
            revenue_date_to=revenue_date_to,
            org_id=org_id,
            business_unit_id=business_unit_id,
            division_id=division_id,
            revenue_type_id=revenue_type_id,
            customer_id=customer_id,
            reporting_currency_code=reporting_currency.upper() if reporting_currency else None,
            include_native_amounts=include_native_amounts,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "FX_RATE_MISSING",
                    "message": "No FX rate for conversion — upload rates or use native rollup.",
                    "details": None,
                }
            },
        ) from None
    return payload


@router.get(
    "/profitability/summary",
    summary="Profitability summary",
    description="Phase 5 — revenue from fact_revenue and costs from fact_cost.",
    dependencies=[Depends(require_phase5_enabled)],
)
async def get_profitability_summary(
    period_start: date = Query(...),
    period_end: date = Query(...),
    org_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    customer_id: UUID | None = None,
    cost_scope: str = Query("cogs_only", description="cogs_only | fully_loaded"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if cost_scope not in ("cogs_only", "fully_loaded"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Invalid cost_scope", "details": None}},
        )
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id is not None and org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Org not accessible", "details": None}},
        )
    payload, _ = await profitability_summary(
        session,
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        period_start=period_start,
        period_end=period_end,
        org_id=org_id,
        business_unit_id=business_unit_id,
        customer_id=customer_id,
        cost_scope=cost_scope,
    )
    return payload


@router.get(
    "/revenue/forecast-vs-actual",
    summary="Forecast vs actual comparison",
    description="Phase 5 — explicit separation of booked actuals vs forecast series.",
    dependencies=[Depends(require_phase5_enabled)],
)
async def get_forecast_vs_actual(
    forecast_series_id: UUID = Query(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
    org_id: UUID | None = None,
    hierarchy: str = Query("org"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if hierarchy not in PHASE5_HIERARCHY_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "forecast vs actual supports org | bu | division only",
                    "details": None,
                }
            },
        )
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id is not None and org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Org not accessible", "details": None}},
        )
    try:
        return await forecast_vs_actual(
            session,
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            forecast_series_id=forecast_series_id,
            period_start=period_start,
            period_end=period_end,
            org_id=org_id,
            hierarchy=hierarchy,  # type: ignore[arg-type]
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Forecast series not found", "details": None}},
        ) from None
