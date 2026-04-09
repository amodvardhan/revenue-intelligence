"""Revenue facts + customer matrix (facts, manual cell overrides, MoM display)."""

from __future__ import annotations

import base64
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_phase7_enabled
from app.models.dimensions import DimBusinessUnit, DimCustomer, DimDivision
from app.models.facts import FactRevenue
from app.models.phase7 import RevenueManualCell, RevenueVarianceComment
from app.models.tenant import User
from app.schemas.revenue import (
    MatrixCellUpsertBody,
    RevenueListResponse,
    RevenueMatrixResponse,
    RevenueRow,
    VarianceCommentPromptListResponse,
    VarianceCommentUpsertBody,
)
from app.services.access_scope import accessible_org_ids, business_unit_scope
from app.services.revenue.matrix_permissions import (
    can_write_manual_matrix_cell,
    dm_assigned_customer_ids,
    matrix_edit_flags,
)
from app.services.revenue.matrix_service import build_revenue_matrix
from app.services.revenue.variance_comment_service import VARIANCE_COMMENT_MAX_LEN, list_dm_variance_prompts

router = APIRouter(prefix="/revenue", tags=["revenue"])


def _amount_str(d: Decimal) -> str:
    """Serialize money as plain decimal string (no scientific notation)."""
    return format(d, "f")


def _decode_cursor(cursor: str | None) -> int:
    """Opaque cursor carries JSON `{"o": offset}` base64url-encoded."""
    if not cursor:
        return 0
    try:
        pad = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + pad)
        data = json.loads(raw.decode())
        return max(0, int(data.get("o", 0)))
    except (ValueError, json.JSONDecodeError, TypeError):
        return 0


def _encode_cursor(offset: int) -> str | None:
    if offset <= 0:
        return None
    raw = json.dumps({"o": offset}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


@router.get(
    "/matrix",
    response_model=RevenueMatrixResponse,
    dependencies=[Depends(require_phase7_enabled)],
    summary="Customer × month matrix (workbook layout)",
    description="Pivots facts with customers into Sr. No., names, and month columns; "
    "adds a computed MoM delta row per customer. Optional BU/division filters scope the grid. "
    "Manual cell overrides replace the fact total for the same scope.",
)
async def revenue_customer_matrix(
    org_id: UUID = Query(..., description="Organization scope"),
    revenue_date_from: date | None = Query(None),
    revenue_date_to: date | None = Query(None),
    business_unit_id: UUID | None = Query(None, description="Optional: filter matrix to this BU"),
    division_id: UUID | None = Query(None, description="Optional: filter matrix to this division"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RevenueMatrixResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id not in accessible:
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

    mode, bu_ids = await business_unit_scope(session, user.user_id)
    restricted = mode == "restricted"
    bu_set = set(bu_ids)

    if division_id is not None and business_unit_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "division_id requires business_unit_id",
                    "details": None,
                }
            },
        )

    allow_edit, dm_ids = await matrix_edit_flags(session, user, org_id)
    return await build_revenue_matrix(
        session,
        user=user,
        org_id=org_id,
        revenue_date_from=revenue_date_from,
        revenue_date_to=revenue_date_to,
        business_unit_id=business_unit_id,
        division_id=division_id,
        restricted=restricted,
        restricted_bu_ids=bu_set,
        allow_matrix_full_edit=allow_edit,
        dm_editable_customers=dm_ids,
    )


@router.put(
    "/matrix/cell",
    response_model=RevenueMatrixResponse,
    dependencies=[Depends(require_phase7_enabled)],
    summary="Upsert manual matrix cell (correct or enter monthly revenue)",
)
async def upsert_matrix_cell(
    body: MatrixCellUpsertBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RevenueMatrixResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if body.org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    if not await can_write_manual_matrix_cell(
        session,
        user,
        body.org_id,
        body.customer_id,
        body.business_unit_id,
        body.division_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role to edit matrix", "details": None}},
        )

    if body.division_id is not None and body.business_unit_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "division_id requires business_unit_id", "details": None}},
        )

    try:
        amount = Decimal(body.amount.strip().replace(",", ""))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid amount: {exc}", "details": None}},
        ) from exc

    month = _month_start(body.revenue_month)

    cust = await session.scalar(
        select(DimCustomer).where(
            DimCustomer.customer_id == body.customer_id,
            DimCustomer.tenant_id == user.tenant_id,
        )
    )
    if cust is None or cust.org_id != body.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Customer not found for this organization", "details": None}},
        )

    if body.business_unit_id is not None:
        bu = await session.scalar(
            select(DimBusinessUnit).where(
                DimBusinessUnit.business_unit_id == body.business_unit_id,
                DimBusinessUnit.tenant_id == user.tenant_id,
                DimBusinessUnit.org_id == body.org_id,
            )
        )
        if bu is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Business unit not in organization", "details": None}},
            )
    if body.division_id is not None:
        div = await session.scalar(
            select(DimDivision).where(
                DimDivision.division_id == body.division_id,
                DimDivision.tenant_id == user.tenant_id,
                DimDivision.business_unit_id == body.business_unit_id,
            )
        )
        if div is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Division not under selected BU", "details": None}},
            )

    res = await session.execute(
        select(RevenueManualCell).where(
            RevenueManualCell.tenant_id == user.tenant_id,
            RevenueManualCell.org_id == body.org_id,
            RevenueManualCell.customer_id == body.customer_id,
            RevenueManualCell.revenue_month == month,
        )
    )
    existing = None
    for row in res.scalars().all():
        if row.business_unit_id == body.business_unit_id and row.division_id == body.division_id:
            existing = row
            break

    if existing is None:
        session.add(
            RevenueManualCell(
                tenant_id=user.tenant_id,
                org_id=body.org_id,
                customer_id=body.customer_id,
                revenue_month=month,
                business_unit_id=body.business_unit_id,
                division_id=body.division_id,
                amount=amount,
                currency_code="USD",
                updated_by_user_id=user.user_id,
            )
        )
    else:
        existing.amount = amount
        existing.updated_by_user_id = user.user_id

    await session.commit()

    mode, bu_ids = await business_unit_scope(session, user.user_id)
    allow_edit, dm_ids = await matrix_edit_flags(session, user, body.org_id)
    return await build_revenue_matrix(
        session,
        user=user,
        org_id=body.org_id,
        revenue_date_from=None,
        revenue_date_to=None,
        business_unit_id=body.business_unit_id,
        division_id=body.division_id,
        restricted=mode == "restricted",
        restricted_bu_ids=set(bu_ids),
        allow_matrix_full_edit=allow_edit,
        dm_editable_customers=dm_ids,
    )


@router.put(
    "/matrix/variance-comment",
    response_model=RevenueMatrixResponse,
    dependencies=[Depends(require_phase7_enabled)],
    summary="Add or update variance narrative for a customer-month (MoM delta column)",
    description="Same scope rules as manual matrix cells: finance and bu_head may use BU/division scope; "
    "delivery managers only org-wide for assigned customers.",
)
async def upsert_variance_comment(
    body: VarianceCommentUpsertBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RevenueMatrixResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if body.org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    if not await can_write_manual_matrix_cell(
        session,
        user,
        body.org_id,
        body.customer_id,
        body.business_unit_id,
        body.division_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role to add variance narrative", "details": None}},
        )

    if body.division_id is not None and body.business_unit_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "division_id requires business_unit_id", "details": None}},
        )

    text = body.comment_text.strip()
    if len(text) > VARIANCE_COMMENT_MAX_LEN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Comment exceeds {VARIANCE_COMMENT_MAX_LEN} characters",
                    "details": None,
                }
            },
        )

    month = _month_start(body.revenue_month)

    cust = await session.scalar(
        select(DimCustomer).where(
            DimCustomer.customer_id == body.customer_id,
            DimCustomer.tenant_id == user.tenant_id,
        )
    )
    if cust is None or cust.org_id != body.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Customer not found for this organization", "details": None}},
        )

    if body.business_unit_id is not None:
        bu = await session.scalar(
            select(DimBusinessUnit).where(
                DimBusinessUnit.business_unit_id == body.business_unit_id,
                DimBusinessUnit.tenant_id == user.tenant_id,
                DimBusinessUnit.org_id == body.org_id,
            )
        )
        if bu is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Business unit not in organization", "details": None}},
            )
    if body.division_id is not None:
        div = await session.scalar(
            select(DimDivision).where(
                DimDivision.division_id == body.division_id,
                DimDivision.tenant_id == user.tenant_id,
                DimDivision.business_unit_id == body.business_unit_id,
            )
        )
        if div is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Division not under selected BU", "details": None}},
            )

    res = await session.execute(
        select(RevenueVarianceComment).where(
            RevenueVarianceComment.tenant_id == user.tenant_id,
            RevenueVarianceComment.org_id == body.org_id,
            RevenueVarianceComment.customer_id == body.customer_id,
            RevenueVarianceComment.revenue_month == month,
        )
    )
    existing = None
    for row in res.scalars().all():
        if row.business_unit_id == body.business_unit_id and row.division_id == body.division_id:
            existing = row
            break

    if not text:
        if existing is not None:
            await session.execute(
                delete(RevenueVarianceComment).where(
                    RevenueVarianceComment.variance_comment_id == existing.variance_comment_id
                )
            )
            await session.commit()
    elif existing is None:
        session.add(
            RevenueVarianceComment(
                tenant_id=user.tenant_id,
                org_id=body.org_id,
                customer_id=body.customer_id,
                revenue_month=month,
                business_unit_id=body.business_unit_id,
                division_id=body.division_id,
                comment_text=text,
                updated_by_user_id=user.user_id,
            )
        )
        await session.commit()
    else:
        existing.comment_text = text
        existing.updated_by_user_id = user.user_id
        await session.commit()

    mode, bu_ids = await business_unit_scope(session, user.user_id)
    allow_edit, dm_ids = await matrix_edit_flags(session, user, body.org_id)
    return await build_revenue_matrix(
        session,
        user=user,
        org_id=body.org_id,
        revenue_date_from=None,
        revenue_date_to=None,
        business_unit_id=body.business_unit_id,
        division_id=body.division_id,
        restricted=mode == "restricted",
        restricted_bu_ids=set(bu_ids),
        allow_matrix_full_edit=allow_edit,
        dm_editable_customers=dm_ids,
    )


@router.get(
    "/variance-comment-prompts",
    response_model=VarianceCommentPromptListResponse,
    dependencies=[Depends(require_phase7_enabled)],
    summary="Months needing a variance narrative (assigned delivery managers)",
    description="Lists customer-months with material MoM or YoY movement and no narrative yet; "
    "only includes customers the current user actively manages.",
)
async def variance_comment_prompts(
    org_id: UUID = Query(..., description="Organization scope"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> VarianceCommentPromptListResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    dm_ids = await dm_assigned_customer_ids(
        session, tenant_id=user.tenant_id, org_id=org_id, user_id=user.user_id
    )
    items = await list_dm_variance_prompts(session, user=user, org_id=org_id, dm_customer_ids=dm_ids)
    return VarianceCommentPromptListResponse(items=items)


@router.delete(
    "/matrix/cell",
    response_model=RevenueMatrixResponse,
    dependencies=[Depends(require_phase7_enabled)],
    summary="Remove manual override for a matrix cell (revert to imported fact totals)",
)
async def delete_matrix_cell(
    org_id: UUID = Query(...),
    customer_id: UUID = Query(...),
    revenue_month: date = Query(..., description="Any date in the month"),
    business_unit_id: UUID | None = Query(None),
    division_id: UUID | None = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RevenueMatrixResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    if not await can_write_manual_matrix_cell(
        session, user, org_id, customer_id, business_unit_id, division_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role to edit matrix", "details": None}},
        )
    if division_id is not None and business_unit_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "division_id requires business_unit_id", "details": None}},
        )

    month = _month_start(revenue_month)
    res = await session.execute(
        select(RevenueManualCell).where(
            RevenueManualCell.tenant_id == user.tenant_id,
            RevenueManualCell.org_id == org_id,
            RevenueManualCell.customer_id == customer_id,
            RevenueManualCell.revenue_month == month,
        )
    )
    target = None
    for row in res.scalars().all():
        if row.business_unit_id == business_unit_id and row.division_id == division_id:
            target = row
            break
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "No manual cell for this scope", "details": None}},
        )
    session.delete(target)
    await session.commit()

    mode, bu_ids = await business_unit_scope(session, user.user_id)
    allow_edit, dm_ids = await matrix_edit_flags(session, user, org_id)
    return await build_revenue_matrix(
        session,
        user=user,
        org_id=org_id,
        revenue_date_from=None,
        revenue_date_to=None,
        business_unit_id=business_unit_id,
        division_id=division_id,
        restricted=mode == "restricted",
        restricted_bu_ids=set(bu_ids),
        allow_matrix_full_edit=allow_edit,
        dm_editable_customers=dm_ids,
    )


@router.get(
    "",
    response_model=RevenueListResponse,
    summary="List revenue facts",
    description="Tenant-scoped facts filtered by orgs the user may access (user_org_role). "
    "Phase 2: optional BU restriction via user_business_unit_access; drill-down filters. "
    "Amounts are decimal strings. Pagination via limit and opaque cursor.",
)
async def list_revenue(
    org_id: UUID | None = Query(None, description="Filter to this organization"),
    business_unit_id: UUID | None = None,
    division_id: UUID | None = None,
    revenue_type_id: UUID | None = None,
    customer_id: UUID | None = None,
    revenue_date_from: date | None = None,
    revenue_date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RevenueListResponse:
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

    org_scope = {org_id} if org_id is not None else accessible
    if not org_scope:
        return RevenueListResponse(items=[], next_cursor=None)

    mode, bu_ids = await business_unit_scope(session, user.user_id)
    restricted = mode == "restricted"

    offset = _decode_cursor(cursor)
    stmt = (
        select(FactRevenue)
        .where(
            FactRevenue.tenant_id == user.tenant_id,
            FactRevenue.org_id.in_(org_scope),
            FactRevenue.is_deleted.is_(False),
        )
        .order_by(FactRevenue.revenue_date.desc(), FactRevenue.revenue_id.desc())
    )
    if restricted:
        stmt = stmt.where(
            and_(
                FactRevenue.business_unit_id.isnot(None),
                FactRevenue.business_unit_id.in_(bu_ids),
            )
        )
    if business_unit_id is not None:
        stmt = stmt.where(FactRevenue.business_unit_id == business_unit_id)
    if division_id is not None:
        stmt = stmt.where(FactRevenue.division_id == division_id)
    if revenue_type_id is not None:
        stmt = stmt.where(FactRevenue.revenue_type_id == revenue_type_id)
    if customer_id is not None:
        stmt = stmt.where(FactRevenue.customer_id == customer_id)
    if revenue_date_from is not None:
        stmt = stmt.where(FactRevenue.revenue_date >= revenue_date_from)
    if revenue_date_to is not None:
        stmt = stmt.where(FactRevenue.revenue_date <= revenue_date_to)

    fetch = limit + 1
    stmt = stmt.offset(offset).limit(fetch)
    res = await session.execute(stmt)
    rows = list(res.scalars().all())

    has_more = len(rows) > limit
    page = rows[:limit]
    next_c = _encode_cursor(offset + limit) if has_more else None

    items = [
        RevenueRow(
            revenue_id=r.revenue_id,
            amount=_amount_str(r.amount),
            currency_code=r.currency_code,
            revenue_date=r.revenue_date,
            org_id=r.org_id,
            business_unit_id=r.business_unit_id,
            division_id=r.division_id,
            customer_id=r.customer_id,
            revenue_type_id=r.revenue_type_id,
            source_system=r.source_system,
            batch_id=r.batch_id,
        )
        for r in page
    ]
    return RevenueListResponse(items=items, next_cursor=next_c)
