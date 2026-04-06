"""Customer segments (Phase 5)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_user,
    require_phase5_enabled,
    require_phase5_upload_role,
    require_segment_definition_role,
)
from app.models.dimensions import DimCustomer
from app.models.phase5 import SegmentDefinition, SegmentMembership
from app.models.tenant import User
from app.services.access_scope import accessible_org_ids
from app.services.segments.service import materialize_segment_membership

router = APIRouter(prefix="/segments", tags=["segments"])


@router.get(
    "/definitions",
    summary="List segment definitions",
    dependencies=[Depends(require_phase5_enabled)],
)
async def list_segment_definitions(
    org_id: UUID | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    limit = min(max(limit, 1), 200)
    stmt = select(SegmentDefinition).where(SegmentDefinition.tenant_id == user.tenant_id)
    if org_id:
        stmt = stmt.where(SegmentDefinition.owner_org_id == org_id)
    if is_active is not None:
        stmt = stmt.where(SegmentDefinition.is_active == is_active)
    stmt = stmt.order_by(SegmentDefinition.updated_at.desc()).limit(limit)
    res = await session.execute(stmt)
    items = []
    for s in res.scalars().all():
        items.append(
            {
                "segment_id": str(s.segment_id),
                "name": s.name,
                "version": s.version,
                "owner_org_id": str(s.owner_org_id) if s.owner_org_id else None,
                "is_active": s.is_active,
                "updated_at": s.updated_at.isoformat().replace("+00:00", "Z"),
            }
        )
    return {"items": items, "next_cursor": None}


@router.post(
    "/definitions",
    summary="Create segment definition",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_phase5_enabled)],
)
async def create_segment_definition(
    body: dict,
    user: User = Depends(require_segment_definition_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    name = str(body.get("name", "")).strip()[:200]
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "name required", "details": None}},
        )
    owner = UUID(body["owner_org_id"]) if body.get("owner_org_id") else None
    seg = SegmentDefinition(
        tenant_id=user.tenant_id,
        name=name,
        rule_definition=body.get("rule_definition") or {},
        owner_org_id=owner,
        created_by_user_id=user.user_id,
    )
    session.add(seg)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Segment name may already exist", "details": None}},
        ) from None
    await session.refresh(seg)
    return {"segment_id": str(seg.segment_id), "version": seg.version}


@router.patch(
    "/definitions/{segment_id}",
    summary="Update segment definition",
    dependencies=[Depends(require_phase5_enabled)],
)
async def patch_segment_definition(
    segment_id: UUID,
    body: dict,
    user: User = Depends(require_segment_definition_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    seg = await session.get(SegmentDefinition, segment_id)
    if seg is None or seg.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Segment not found", "details": None}},
        )
    if "rule_definition" in body and body["rule_definition"] is not None:
        seg.rule_definition = body["rule_definition"]
        seg.version += 1
    if "is_active" in body and body["is_active"] is not None:
        seg.is_active = bool(body["is_active"])
    seg.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"segment_id": str(seg.segment_id), "version": seg.version, "is_active": seg.is_active}


@router.post(
    "/definitions/{segment_id}/materialize",
    summary="Materialize segment membership",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_phase5_enabled)],
)
async def materialize_segment(
    segment_id: UUID,
    body: dict,
    user: User = Depends(require_phase5_upload_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if body.get("as_of_date") and (body.get("period_start") or body.get("period_end")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Use period_start/period_end OR as_of_date, not both",
                    "details": None,
                }
            },
        )
    try:
        if body.get("as_of_date"):
            # v1: materialize as-of not fully implemented — use period where start=end
            ad = date.fromisoformat(body["as_of_date"])
            n = await materialize_segment_membership(
                session,
                tenant_id=user.tenant_id,
                segment_id=segment_id,
                period_start=ad,
                period_end=ad,
            )
        else:
            ps = date.fromisoformat(body["period_start"])
            pe = date.fromisoformat(body["period_end"])
            n = await materialize_segment_membership(
                session,
                tenant_id=user.tenant_id,
                segment_id=segment_id,
                period_start=ps,
                period_end=pe,
            )
        await session.commit()
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Segment not found", "details": None}},
        ) from None
    except ValueError as e:
        if str(e) == "SEGMENT_RULE_INVALID":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "SEGMENT_RULE_INVALID", "message": "Invalid rule", "details": None}},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": None}},
        ) from None
    return {"status": "accepted", "membership_rows": n}


@router.get(
    "/definitions/{segment_id}/membership",
    summary="List segment membership",
    dependencies=[Depends(require_phase5_enabled)],
)
async def list_membership(
    segment_id: UUID,
    period_start: date | None = None,
    period_end: date | None = None,
    as_of_date: date | None = None,
    segment_version: int | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    limit = min(max(limit, 1), 200)
    seg = await session.get(SegmentDefinition, segment_id)
    if seg is None or seg.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Segment not found", "details": None}},
        )
    ver = segment_version if segment_version is not None else seg.version
    f = [
        SegmentMembership.segment_id == segment_id,
        SegmentMembership.segment_version == ver,
    ]
    if period_start and period_end:
        f.append(SegmentMembership.period_start == period_start)
        f.append(SegmentMembership.period_end == period_end)
    if as_of_date:
        f.append(SegmentMembership.as_of_date == as_of_date)
    stmt = (
        select(SegmentMembership, DimCustomer.customer_name)
        .join(DimCustomer, DimCustomer.customer_id == SegmentMembership.customer_id)
        .where(and_(*f))
        .limit(limit)
    )
    res = await session.execute(stmt)
    items = []
    for row, cname in res.all():
        items.append(
            {
                "customer_id": str(row.customer_id),
                "customer_name": cname,
                "period_start": row.period_start.isoformat() if row.period_start else None,
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "as_of_date": row.as_of_date.isoformat() if row.as_of_date else None,
            }
        )
    return {"items": items, "next_cursor": None}
