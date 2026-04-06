"""Orchestrate parse → validate → overlap → load for an ingestion batch."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ImportOverlapError
from app.models.facts import IngestionBatch
from app.models.tenant import Tenant
from app.services.ingestion.excel_parser import parse_excel
from app.services.ingestion.loader import DimensionResolveError, insert_revenue_facts
from app.services.ingestion.overlap import scope_has_overlap, soft_delete_facts_in_scope
from app.services.analytics.refresh import refresh_analytics_structures
from app.services.ingestion.validator import validate_parsed_excel

logger = logging.getLogger(__name__)


async def run_ingestion(
    session: AsyncSession,
    *,
    batch_id: UUID,
    file_content: bytes,
    org_id: UUID,
    scope_org_id: UUID | None,
    period_start: date | None,
    period_end: date | None,
    replace: bool,
) -> IngestionBatch:
    """Execute the pipeline; commits batch terminal state."""
    result = await session.execute(select(IngestionBatch).where(IngestionBatch.batch_id == batch_id))
    batch = result.scalar_one_or_none()
    if batch is None:
        raise ValueError("batch not found")

    batch.status = "validating"
    await session.flush()

    try:
        parsed = parse_excel(file_content)
    except Exception as e:
        batch.status = "failed"
        batch.error_log = {
            "errors": [{"row": None, "column": None, "message": f"Could not read Excel file: {e}"}]
        }
        batch.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return batch

    v = validate_parsed_excel(parsed)
    if v.errors:
        batch.status = "failed"
        batch.total_rows = len(parsed.rows)
        batch.loaded_rows = 0
        batch.error_rows = len(parsed.rows)
        batch.error_log = {"errors": v.errors}
        batch.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return batch

    rows = v.rows
    ps = period_start or min(r.revenue_date for r in rows)
    pe = period_end or max(r.revenue_date for r in rows)
    grain_org = scope_org_id or org_id

    tenant_res = await session.execute(select(Tenant).where(Tenant.tenant_id == batch.tenant_id))
    tenant = tenant_res.scalar_one()
    currency = tenant.default_currency_code

    overlap = await scope_has_overlap(
        session,
        tenant_id=batch.tenant_id,
        scope_org_id=grain_org,
        period_start=ps,
        period_end=pe,
    )
    if overlap and not replace:
        batch.status = "rejected"
        batch.error_log = {
            "errors": [
                {
                    "row": None,
                    "column": None,
                    "message": "Import overlaps existing data for this scope and period. "
                    "Use replace=true to replace.",
                }
            ]
        }
        batch.period_start = ps
        batch.period_end = pe
        batch.scope_org_id = grain_org
        batch.completed_at = datetime.now(timezone.utc)
        await session.commit()
        raise ImportOverlapError("overlap")

    batch.status = "loading"
    batch.period_start = ps
    batch.period_end = pe
    batch.scope_org_id = grain_org
    batch.total_rows = len(rows)
    await session.flush()

    if replace:
        await soft_delete_facts_in_scope(
            session,
            tenant_id=batch.tenant_id,
            org_id=org_id,
            period_start=ps,
            period_end=pe,
        )

    try:
        async with session.begin_nested():
            loaded = await insert_revenue_facts(
                session,
                batch_id=batch.batch_id,
                tenant_id=batch.tenant_id,
                org_id=org_id,
                currency_code=currency,
                validated_rows=rows,
            )
    except DimensionResolveError as e:
        batch = await session.get(IngestionBatch, batch_id)
        if batch is not None:
            batch.status = "failed"
            batch.error_log = {
                "errors": [{"row": None, "column": None, "message": str(e)}],
            }
            batch.loaded_rows = 0
            batch.error_rows = batch.total_rows or 0
            batch.completed_at = datetime.now(timezone.utc)
            await session.commit()
        return batch  # type: ignore[unreachable]

    batch.status = "completed"
    batch.loaded_rows = loaded
    batch.error_rows = 0
    batch.completed_at = datetime.now(timezone.utc)
    await session.commit()
    try:
        await refresh_analytics_structures(
            session,
            tenant_id=batch.tenant_id,
            batch_id=batch.batch_id,
        )
    except Exception:
        logger.exception("analytics refresh after ingest failed batch=%s", batch.batch_id)
    return batch


def read_uploaded_file(storage_key: str | None) -> bytes:
    """Read bytes from a local temp path written at upload time."""
    if not storage_key or not storage_key.startswith("file://"):
        raise ValueError("invalid storage key")
    path = Path(storage_key.removeprefix("file://"))
    return path.read_bytes()
