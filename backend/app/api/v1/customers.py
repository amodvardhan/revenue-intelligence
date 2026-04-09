"""Create and list customers (dim_customer) for an organization."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import PROJECT_WRITE_ROLES, get_current_user, org_role_allowed
from app.models.dimensions import DimCustomer
from app.models.tenant import User
from app.schemas.customer import CreateCustomerBody, CustomerItem, CustomerListResponse
from app.services.access_scope import accessible_org_ids

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
    res = await session.execute(
        select(
            DimCustomer.customer_id,
            DimCustomer.customer_name,
            DimCustomer.customer_name_common,
            DimCustomer.customer_code,
        ).where(
            DimCustomer.tenant_id == user.tenant_id,
            DimCustomer.org_id == org_id,
            DimCustomer.is_active.is_(True),
        ).order_by(DimCustomer.customer_name)
    )
    items = [
        CustomerItem(
            customer_id=r[0],
            customer_name=r[1],
            customer_name_common=(r[2] or "").strip() or None,
            customer_code=r[3],
        )
        for r in res.all()
    ]
    return CustomerListResponse(items=items)


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

    common = (body.customer_name_common or "").strip() or None
    code = (body.customer_code or "").strip() or None
    row = DimCustomer(
        tenant_id=user.tenant_id,
        org_id=body.org_id,
        customer_name=body.customer_name.strip(),
        customer_name_common=common or body.customer_name.strip(),
        customer_code=code,
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
    return CustomerItem(
        customer_id=row.customer_id,
        customer_name=row.customer_name,
        customer_name_common=(row.customer_name_common or "").strip() or None,
        customer_code=row.customer_code,
    )
