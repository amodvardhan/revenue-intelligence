"""FX rates — manual upload (Phase 5)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_phase5_enabled, require_phase5_upload_role
from app.models.facts import IngestionBatch
from app.models.phase5 import FxRate
from app.models.tenant import User
from app.services.fx.csv_ingest import load_fx_csv

router = APIRouter(prefix="/fx-rates", tags=["fx-rates"])


@router.get(
    "",
    summary="List FX rates",
    dependencies=[Depends(require_phase5_enabled)],
)
async def list_fx_rates(
    effective_from: date | None = None,
    effective_to: date | None = None,
    base_currency_code: str | None = None,
    quote_currency_code: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    limit = min(max(limit, 1), 200)
    stmt = select(FxRate).where(FxRate.tenant_id == user.tenant_id)
    if effective_from:
        stmt = stmt.where(FxRate.effective_date >= effective_from)
    if effective_to:
        stmt = stmt.where(FxRate.effective_date <= effective_to)
    if base_currency_code:
        stmt = stmt.where(FxRate.base_currency_code == base_currency_code.upper()[:3])
    if quote_currency_code:
        stmt = stmt.where(FxRate.quote_currency_code == quote_currency_code.upper()[:3])
    stmt = stmt.order_by(FxRate.effective_date.desc()).limit(limit)
    res = await session.execute(stmt)
    items = []
    for r in res.scalars().all():
        items.append(
            {
                "fx_rate_id": str(r.fx_rate_id),
                "base_currency_code": r.base_currency_code,
                "quote_currency_code": r.quote_currency_code,
                "effective_date": r.effective_date.isoformat(),
                "rate": format(r.rate, "f"),
                "rate_source": r.rate_source,
                "ingestion_batch_id": str(r.ingestion_batch_id) if r.ingestion_batch_id else None,
                "created_at": r.created_at.isoformat().replace("+00:00", "Z"),
            }
        )
    return {"items": items, "next_cursor": None}


@router.post(
    "/uploads",
    summary="Upload FX rates CSV",
    dependencies=[Depends(require_phase5_enabled)],
)
async def upload_fx_rates(
    file: UploadFile = File(...),
    notes: str | None = Form(None),
    user: User = Depends(require_phase5_upload_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Filename required", "details": None}},
        )
    content = await file.read()
    batch = IngestionBatch(
        tenant_id=user.tenant_id,
        source_system="fx_upload",
        filename=file.filename,
        initiated_by=user.user_id,
        status="pending",
    )
    session.add(batch)
    await session.flush()
    try:
        n = await load_fx_csv(
            session,
            tenant_id=user.tenant_id,
            file_bytes=content,
            batch_id=batch.batch_id,
            rate_source="manual_upload",
        )
        batch.status = "completed"
        batch.loaded_rows = n
        batch.total_rows = n
        batch.completed_at = datetime.now(timezone.utc)
        if notes:
            batch.error_log = {"notes": notes}
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "IMPORT_OVERLAP",
                    "message": "Duplicate or conflicting FX rate row",
                    "details": None,
                }
            },
        ) from None
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": None}},
        ) from None

    return {
        "batch_id": str(batch.batch_id),
        "status": "completed",
        "total_rows": n,
        "loaded_rows": n,
    }
