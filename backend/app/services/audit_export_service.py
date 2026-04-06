"""Cross-table audit evidence export (CSV / JSON Lines)."""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent, QueryAuditLog
from app.models.facts import IngestionBatch
from app.models.hubspot_integration import IntegrationSyncRun
from app.models.tenant import User


async def collect_audit_export_rows(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    event_families: list[str],
    created_from: datetime,
    created_to: datetime,
    max_rows: int,
) -> list[dict[str, Any]]:
    """Return up to max_rows uniform dict rows across selected families (ordered by recency per family)."""
    rows: list[dict[str, Any]] = []

    if "ingestion" in event_families and len(rows) < max_rows:
        stmt = (
            select(IngestionBatch, User.email)
            .outerjoin(User, User.user_id == IngestionBatch.initiated_by)
            .where(
                IngestionBatch.tenant_id == tenant_id,
                IngestionBatch.created_at >= created_from,
                IngestionBatch.created_at <= created_to,
            )
            .order_by(IngestionBatch.created_at.desc())
            .limit(max_rows - len(rows))
        )
        res = await session.execute(stmt)
        for batch, email in res.all():
            rows.append(
                {
                    "family": "ingestion",
                    "id": str(batch.batch_id),
                    "created_at": batch.created_at.isoformat(),
                    "user_id": str(batch.initiated_by) if batch.initiated_by else "",
                    "user_email": email or "",
                    "status": batch.status,
                    "source_system": batch.source_system,
                    "filename": batch.filename or "",
                }
            )

    if "nl_query" in event_families and len(rows) < max_rows:
        stmt = (
            select(QueryAuditLog, User.email)
            .outerjoin(User, User.user_id == QueryAuditLog.user_id)
            .where(
                QueryAuditLog.tenant_id == tenant_id,
                QueryAuditLog.created_at >= created_from,
                QueryAuditLog.created_at <= created_to,
            )
            .order_by(QueryAuditLog.created_at.desc())
            .limit(max_rows - len(rows))
        )
        res = await session.execute(stmt)
        for log, email in res.all():
            rows.append(
                {
                    "family": "nl_query",
                    "id": str(log.log_id),
                    "created_at": log.created_at.isoformat(),
                    "user_id": str(log.user_id) if log.user_id else "",
                    "user_email": email or "",
                    "natural_query": log.natural_query[:2000],
                    "status": log.status or "",
                    "row_count": log.row_count,
                }
            )

    if "hubspot_sync" in event_families and len(rows) < max_rows:
        stmt = (
            select(IntegrationSyncRun, User.email)
            .outerjoin(User, User.user_id == IntegrationSyncRun.initiated_by_user_id)
            .where(
                IntegrationSyncRun.tenant_id == tenant_id,
                IntegrationSyncRun.started_at >= created_from,
                IntegrationSyncRun.started_at <= created_to,
            )
            .order_by(IntegrationSyncRun.started_at.desc())
            .limit(max_rows - len(rows))
        )
        res = await session.execute(stmt)
        for run, email in res.all():
            rows.append(
                {
                    "family": "hubspot_sync",
                    "id": str(run.sync_run_id),
                    "created_at": run.started_at.isoformat(),
                    "user_id": str(run.initiated_by_user_id) if run.initiated_by_user_id else "",
                    "user_email": email or "",
                    "status": run.status,
                    "integration_code": run.integration_code,
                    "error_summary": (run.error_summary or "")[:2000],
                }
            )

    if "sso_security" in event_families and len(rows) < max_rows:
        stmt = (
            select(AuditEvent, User.email)
            .outerjoin(User, User.user_id == AuditEvent.user_id)
            .where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.created_at >= created_from,
                AuditEvent.created_at <= created_to,
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(max_rows - len(rows))
        )
        res = await session.execute(stmt)
        for ev, email in res.all():
            rows.append(
                {
                    "family": "sso_security",
                    "id": str(ev.event_id),
                    "created_at": ev.created_at.isoformat(),
                    "user_id": str(ev.user_id) if ev.user_id else "",
                    "user_email": email or "",
                    "action": ev.action,
                    "entity_type": ev.entity_type,
                    "entity_id": str(ev.entity_id),
                }
            )

    return rows[:max_rows]


def rows_to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    fieldnames = sorted({k for r in rows for k in r})
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fieldnames})
    return buf.getvalue().encode("utf-8")


def rows_to_jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(r, default=str) + "\n" for r in rows]
    return "".join(lines).encode("utf-8")
