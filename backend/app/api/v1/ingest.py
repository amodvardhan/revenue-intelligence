"""Excel ingestion upload and batch status."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_ingest_role
from app.core.exceptions import ImportOverlapError
from app.models.facts import IngestionBatch
from app.models.tenant import User
from app.schemas.ingest import (
    BatchDetailResponse,
    BatchListItem,
    BatchListResponse,
    UploadAsyncResponse,
    UploadSyncFailedResponse,
    UploadSyncSuccessResponse,
)
from app.services.ingestion.ingestion_service import run_ingestion
from app.tasks.ingest_tasks import process_ingest_batch

router = APIRouter(prefix="/ingest", tags=["ingestion"])


def _parse_replace(v: str | None) -> bool:
    if v is None:
        return False
    return v.lower() in ("true", "1", "yes")


def _parse_date(v: str | None) -> date | None:
    if v is None or v == "":
        return None
    return date.fromisoformat(v)


@router.post(
    "/uploads",
    summary="Upload Excel revenue file",
    description="Multipart upload with org scope and optional period/replace. "
    "Small files process synchronously; large files return 202 and process asynchronously.",
)
async def upload_excel(
    response: Response,
    file: UploadFile = File(..., description="Excel .xlsx or .xls"),
    org_id: UUID = Form(..., description="Target organization for facts"),
    scope_org_id: UUID | None = Form(None),
    period_start: str | None = Form(None),
    period_end: str | None = Form(None),
    replace: str | None = Form(None),
    user: User = Depends(require_ingest_role),
    session: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Filename required", "details": None}},
        )
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".xlsx", ".xls"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Unsupported file type", "details": None}},
        )

    content = await file.read()
    if len(content) > settings.INGEST_SYNC_MAX_BYTES * 2:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "File exceeds max size", "details": None}},
        )

    ps = _parse_date(period_start)
    pe = _parse_date(period_end)
    rep = _parse_replace(replace)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    storage_key = f"file://{tmp_path}"

    batch = IngestionBatch(
        tenant_id=user.tenant_id,
        source_system="excel",
        filename=file.filename,
        storage_key=storage_key,
        initiated_by=user.user_id,
        status="pending",
    )
    session.add(batch)
    await session.flush()

    if len(content) <= settings.INGEST_SYNC_MAX_BYTES:
        result: IngestionBatch | None = None
        try:
            result = await run_ingestion(
                session,
                batch_id=batch.batch_id,
                file_content=content,
                org_id=org_id,
                scope_org_id=scope_org_id,
                period_start=ps,
                period_end=pe,
                replace=rep,
            )
        except ImportOverlapError:
            b = await session.get(IngestionBatch, batch.batch_id)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "IMPORT_OVERLAP",
                        "message": "Overlapping import scope",
                        "details": {"batch_id": str(b.batch_id) if b else None},
                    }
                },
            ) from None
        finally:
            if Path(tmp_path).exists():
                Path(tmp_path).unlink(missing_ok=True)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"code": "INTERNAL", "message": "Ingestion did not return a result", "details": None}},
            )

        if result.status in ("failed", "rejected"):
            return UploadSyncFailedResponse(
                batch_id=result.batch_id,
                status="failed",
                total_rows=result.total_rows,
                loaded_rows=result.loaded_rows,
                error_log=result.error_log or {"errors": []},
            )
        return UploadSyncSuccessResponse(
            batch_id=result.batch_id,
            status="completed",
            total_rows=result.total_rows,
            loaded_rows=result.loaded_rows,
            period_start=result.period_start,
            period_end=result.period_end,
        )

    await session.commit()
    response.status_code = status.HTTP_202_ACCEPTED
    process_ingest_batch.delay(
        str(batch.batch_id),
        str(org_id),
        str(scope_org_id) if scope_org_id else "",
        period_start or "",
        period_end or "",
        rep,
    )
    return UploadAsyncResponse(batch_id=batch.batch_id, status="pending", message="Processing in background")


@router.get(
    "/batches",
    response_model=BatchListResponse,
    summary="List ingestion batches",
)
async def list_batches(
    status_filter: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BatchListResponse:
    limit = min(max(limit, 1), 200)
    stmt = select(IngestionBatch).where(IngestionBatch.tenant_id == user.tenant_id)
    if status_filter:
        stmt = stmt.where(IngestionBatch.status == status_filter)
    stmt = stmt.order_by(IngestionBatch.started_at.desc()).limit(limit)
    res = await session.execute(stmt)
    items = [
        BatchListItem(
            batch_id=b.batch_id,
            source_system=b.source_system,
            filename=b.filename,
            status=b.status,
            total_rows=b.total_rows,
            loaded_rows=b.loaded_rows,
            error_rows=b.error_rows,
            started_at=b.started_at,
            completed_at=b.completed_at,
        )
        for b in res.scalars().all()
    ]
    return BatchListResponse(items=items, next_cursor=None)


@router.get(
    "/batches/{batch_id}",
    response_model=BatchDetailResponse,
    summary="Get ingestion batch detail",
)
async def get_batch(
    batch_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BatchDetailResponse:
    res = await session.execute(
        select(IngestionBatch).where(
            IngestionBatch.batch_id == batch_id,
            IngestionBatch.tenant_id == user.tenant_id,
        )
    )
    b = res.scalar_one_or_none()
    if b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Batch not found", "details": None}},
        )
    return BatchDetailResponse(
        batch_id=b.batch_id,
        tenant_id=b.tenant_id,
        source_system=b.source_system,
        filename=b.filename,
        storage_key=b.storage_key,
        status=b.status,
        total_rows=b.total_rows,
        loaded_rows=b.loaded_rows,
        error_rows=b.error_rows,
        error_log=b.error_log,
        period_start=b.period_start,
        period_end=b.period_end,
        scope_org_id=b.scope_org_id,
        initiated_by=b.initiated_by,
        started_at=b.started_at,
        completed_at=b.completed_at,
    )
