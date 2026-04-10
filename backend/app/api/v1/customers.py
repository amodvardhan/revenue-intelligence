"""Create and list customers (dim_customer) for an organization."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database import get_db
from app.core.deps import PROJECT_WRITE_ROLES, get_current_user, org_role_allowed
from app.models.dimensions import DimBusinessUnit, DimCustomer, DimDivision
from app.models.tenant import User
from app.schemas.customer import (
    CreateCustomerBody,
    CustomerItem,
    CustomerListResponse,
    PatchCustomerBody,
)
from app.services.access_scope import accessible_org_ids
from app.services.customer_hierarchy import CustomerHierarchyError, resolve_validated_customer_hierarchy

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="List customers for an organization",
)
async def list_customers(
    org_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CustomerListResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    bu_a = aliased(DimBusinessUnit)
    div_a = aliased(DimDivision)
    res = await session.execute(
        select(
            DimCustomer.customer_id,
            DimCustomer.customer_name,
            DimCustomer.customer_name_common,
            DimCustomer.customer_code,
            DimCustomer.business_unit_id,
            bu_a.business_unit_name,
            DimCustomer.division_id,
            div_a.division_name,
        )
        .outerjoin(bu_a, bu_a.business_unit_id == DimCustomer.business_unit_id)
        .outerjoin(div_a, div_a.division_id == DimCustomer.division_id)
        .where(
            DimCustomer.tenant_id == user.tenant_id,
            DimCustomer.org_id == org_id,
            DimCustomer.is_active.is_(True),
        )
        .order_by(DimCustomer.customer_name)
    )
    items = [
        CustomerItem(
            customer_id=r[0],
            customer_name=r[1],
            customer_name_common=(r[2] or "").strip() or None,
            customer_code=r[3],
            business_unit_id=r[4],
            business_unit_name=r[5],
            division_id=r[6],
            division_name=r[7],
        )
        for r in res.all()
    ]
    return CustomerListResponse(items=items)


def _customer_item_from_row(row: DimCustomer, bu_name: str | None, div_name: str | None) -> CustomerItem:
    return CustomerItem(
        customer_id=row.customer_id,
        customer_name=row.customer_name,
        customer_name_common=(row.customer_name_common or "").strip() or None,
        customer_code=row.customer_code,
        business_unit_id=row.business_unit_id,
        business_unit_name=bu_name,
        division_id=row.division_id,
        division_name=div_name,
    )


@router.post(
    "",
    response_model=CustomerItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer under an organization",
)
async def create_customer(
    body: CreateCustomerBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CustomerItem:
    accessible = await accessible_org_ids(session, user.user_id)
    if body.org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    if not await org_role_allowed(session, user.user_id, body.org_id, PROJECT_WRITE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role to create customers", "details": None}},
        )

    try:
        bu_id, div_id = await resolve_validated_customer_hierarchy(
            session,
            tenant_id=user.tenant_id,
            org_id=body.org_id,
            business_unit_id=body.business_unit_id,
            division_id=body.division_id,
        )
    except CustomerHierarchyError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": None}},
        ) from e

    common = (body.customer_name_common or "").strip() or None
    code = (body.customer_code or "").strip() or None
    row = DimCustomer(
        tenant_id=user.tenant_id,
        org_id=body.org_id,
        customer_name=body.customer_name.strip(),
        customer_name_common=common or body.customer_name.strip(),
        customer_code=code,
        business_unit_id=bu_id,
        division_id=div_id,
        is_active=True,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "Customer code already used in this tenant",
                    "details": None,
                }
            },
        ) from None
    await session.commit()
    await session.refresh(row)
    bu_name = await session.scalar(select(DimBusinessUnit.business_unit_name).where(DimBusinessUnit.business_unit_id == bu_id)) if bu_id else None
    div_name = await session.scalar(select(DimDivision.division_name).where(DimDivision.division_id == div_id)) if div_id else None
    return _customer_item_from_row(row, bu_name, div_name)


@router.patch(
    "/{customer_id}",
    response_model=CustomerItem,
    summary="Update customer commercial hierarchy (BU / division)",
)
async def patch_customer(
    customer_id: UUID,
    body: PatchCustomerBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CustomerItem:
    row = await session.scalar(
        select(DimCustomer).where(
            DimCustomer.customer_id == customer_id,
            DimCustomer.tenant_id == user.tenant_id,
        )
    )
    if row is None or row.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Customer not found", "details": None}},
        )
    accessible = await accessible_org_ids(session, user.user_id)
    if row.org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    if not await org_role_allowed(session, user.user_id, row.org_id, PROJECT_WRITE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role to update customers", "details": None}},
        )

    fs = body.model_fields_set
    next_bu = row.business_unit_id
    next_div = row.division_id
    if "business_unit_id" in fs:
        next_bu = body.business_unit_id
        if next_bu is None:
            next_div = None
        elif row.business_unit_id != next_bu and "division_id" not in fs:
            next_div = None
    if "division_id" in fs:
        next_div = body.division_id

    try:
        bu_id, div_id = await resolve_validated_customer_hierarchy(
            session,
            tenant_id=user.tenant_id,
            org_id=row.org_id,
            business_unit_id=next_bu,
            division_id=next_div,
        )
    except CustomerHierarchyError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": None}},
        ) from e

    row.business_unit_id = bu_id
    row.division_id = div_id
    await session.commit()
    await session.refresh(row)
    bu_name = (
        await session.scalar(select(DimBusinessUnit.business_unit_name).where(DimBusinessUnit.business_unit_id == bu_id))
        if bu_id
        else None
    )
    div_name = (
        await session.scalar(select(DimDivision.division_name).where(DimDivision.division_id == div_id))
        if div_id
        else None
    )
    return _customer_item_from_row(row, bu_name, div_name)
