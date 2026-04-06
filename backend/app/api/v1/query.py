"""Phase 3 — natural language query, audit, semantic layer version."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    require_nl_query_feature_enabled,
    require_nl_query_role,
    require_query_audit_role,
)
from app.models.audit import QueryAuditLog
from app.models.tenant import User
from app.schemas.query import (
    AuditDetailResponse,
    AuditListItem,
    AuditListResponse,
    NaturalLanguageRequest,
)
from app.services.query_engine.exceptions import (
    LlmUnavailableError,
    QueryTimeoutError,
    QueryUnsafeError,
)
from app.services.query_engine.service import run_natural_language_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])

def _decode_cursor(cur: str | None) -> int:
    if not cur:
        return 0
    try:
        pad = "=" * (-len(cur) % 4)
        raw = base64.urlsafe_b64decode(cur + pad)
        data = json.loads(raw.decode())
        return int(data.get("o", 0))
    except (ValueError, json.JSONDecodeError, KeyError):
        return 0


def _encode_cursor(offset: int) -> str:
    raw = json.dumps({"o": offset}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@router.post(
    "/natural-language",
    summary="Natural language revenue query",
    description="Stories 3.1–3.3 — interpret, validate, execute via analytics services; no raw LLM SQL.",
)
async def post_natural_language(
    body: NaturalLanguageRequest,
    _: None = Depends(require_nl_query_feature_enabled),
    user: User = Depends(require_nl_query_role),
    session: AsyncSession = Depends(get_db),
    x_correlation_id: str | None = Header(None, alias="X-Correlation-Id"),
    x_request_id: str | None = Header(None, alias="X-Request-Id"),
) -> dict[str, Any]:
    cid: uuid.UUID | None = None
    for raw in (x_correlation_id, x_request_id):
        if raw:
            try:
                cid = uuid.UUID(raw)
                break
            except ValueError:
                continue

    clar = None
    if body.clarifications:
        clar = [c.model_dump() for c in body.clarifications]

    if body.disambiguation_token and clar is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "clarifications required with disambiguation_token",
                    "details": None,
                }
            },
        )

    try:
        out = await run_natural_language_query(
            session,
            user=user,
            question=body.question,
            org_id=body.org_id,
            disambiguation_token=body.disambiguation_token,
            clarifications=clar,
            correlation_id=cid,
        )
        await session.commit()
        return out
    except HTTPException:
        await session.rollback()
        raise
    except QueryUnsafeError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "QUERY_UNSAFE",
                    "message": str(e),
                    "details": None,
                }
            },
        ) from e
    except QueryTimeoutError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": {
                    "code": "QUERY_TIMEOUT",
                    "message": str(e),
                    "details": None,
                }
            },
        ) from e
    except LlmUnavailableError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "LLM_UNAVAILABLE",
                    "message": str(e),
                    "details": None,
                }
            },
        ) from e
    except Exception:
        await session.rollback()
        logger.exception("NL query failed")
        raise


@router.get(
    "/audit",
    summary="List NL query audit entries",
    description="Story 3.4 — governance list (finance / IT admin).",
)
async def list_query_audit(
    user: User = Depends(require_query_audit_role),
    session: AsyncSession = Depends(get_db),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
) -> AuditListResponse:
    offset = _decode_cursor(cursor)
    stmt = select(QueryAuditLog).where(QueryAuditLog.tenant_id == user.tenant_id)
    if created_from is not None:
        stmt = stmt.where(QueryAuditLog.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(QueryAuditLog.created_at <= created_to)
    if user_id is not None:
        stmt = stmt.where(QueryAuditLog.user_id == user_id)
    if status_filter:
        stmt = stmt.where(QueryAuditLog.status == status_filter)
    stmt = stmt.order_by(QueryAuditLog.created_at.desc()).offset(offset).limit(limit + 1)
    res = await session.execute(stmt)
    rows = list(res.scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    items: list[AuditListItem] = []
    for r in rows:
        nq = r.natural_query
        short_q = nq[:500] + ("…" if len(nq) > 500 else "")
        items.append(
            AuditListItem(
                log_id=r.log_id,
                user_id=r.user_id,
                natural_query=short_q,
                status=r.status,
                row_count=r.row_count,
                execution_ms=r.execution_ms,
                created_at=r.created_at.isoformat().replace("+00:00", "Z"),
                correlation_id=r.correlation_id,
            )
        )
    next_c = _encode_cursor(offset + limit) if has_more else None
    return AuditListResponse(items=items, next_cursor=next_c)


@router.get(
    "/audit/{log_id}",
    summary="NL query audit detail",
)
async def get_query_audit_detail(
    log_id: uuid.UUID,
    user: User = Depends(require_query_audit_role),
    session: AsyncSession = Depends(get_db),
) -> AuditDetailResponse:
    res = await session.execute(
        select(QueryAuditLog).where(
            QueryAuditLog.log_id == log_id,
            QueryAuditLog.tenant_id == user.tenant_id,
        )
    )
    r = res.scalar_one_or_none()
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Audit entry not found",
                    "details": None,
                }
            },
        )
    return AuditDetailResponse(
        log_id=r.log_id,
        tenant_id=r.tenant_id,
        user_id=r.user_id,
        correlation_id=r.correlation_id,
        nl_session_id=r.nl_session_id,
        semantic_version_id=r.semantic_version_id,
        natural_query=r.natural_query,
        resolved_plan=r.resolved_plan,
        execution_ms=r.execution_ms,
        row_count=r.row_count,
        status=r.status,
        error_message=r.error_message,
        created_at=r.created_at.isoformat().replace("+00:00", "Z"),
    )
