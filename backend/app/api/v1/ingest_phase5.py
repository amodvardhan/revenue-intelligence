"""Phase 5 multipart uploads — forecast and cost CSV."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_phase5_upload_role
from app.models.facts import IngestionBatch
from app.models.tenant import User
from app.services.access_scope import accessible_org_ids
from app.services.forecast.service import load_forecast_csv
from app.services.profitability.cost_ingest import load_cost_csv

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post(
    "/forecast-uploads",
    summary="Upload forecast CSV",
    description="Creates a forecast_series and fact_forecast rows. CSV headers: period_start, period_end, amount, currency_code.",
)
async def upload_forecast_csv(
    file: UploadFile = File(...),
    org_id: UUID = Form(...),
    label: str = Form("Imported forecast"),
    scenario: str | None = Form(None),
    user: User = Depends(require_phase5_upload_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    acc = await accessible_org_ids(session, user.user_id)
    if org_id not in acc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Org not accessible", "details": None}},
        )
    content = await file.read()
    batch = IngestionBatch(
        tenant_id=user.tenant_id,
        source_system="forecast_excel",
        filename=file.filename or "forecast.csv",
        initiated_by=user.user_id,
        status="pending",
    )
    session.add(batch)
    await session.flush()
    try:
        sid, loaded = await load_forecast_csv(
            session,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            org_id=org_id,
            file_bytes=content,
            label=label,
            scenario=scenario,
            batch_id=batch.batch_id,
        )
        batch.status = "completed"
        batch.loaded_rows = loaded
        batch.total_rows = loaded
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": None}},
        ) from None

    return {
        "batch_id": str(batch.batch_id),
        "forecast_series_id": str(sid),
        "status": "completed",
        "loaded_rows": loaded,
    }


@router.post(
    "/cost-uploads",
    summary="Upload cost CSV",
    description="Headers: cost_date, amount, currency_code; optional cost_category, business_unit_id, customer_id, external_id.",
)
async def upload_cost_csv(
    file: UploadFile = File(...),
    org_id: UUID = Form(...),
    cost_category: str = Form("cogs"),
    user: User = Depends(require_phase5_upload_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    acc = await accessible_org_ids(session, user.user_id)
    if org_id not in acc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Org not accessible", "details": None}},
        )
    content = await file.read()
    batch = IngestionBatch(
        tenant_id=user.tenant_id,
        source_system="cost_excel",
        filename=file.filename or "cost.csv",
        initiated_by=user.user_id,
        status="pending",
    )
    session.add(batch)
    await session.flush()
    try:
        loaded = await load_cost_csv(
            session,
            tenant_id=user.tenant_id,
            org_id=org_id,
            default_category=cost_category[:100],
            file_bytes=content,
            batch_id=batch.batch_id,
        )
        batch.status = "completed"
        batch.loaded_rows = loaded
        batch.total_rows = loaded
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": None}},
        ) from None

    return {"batch_id": str(batch.batch_id), "status": "completed", "loaded_rows": loaded}
