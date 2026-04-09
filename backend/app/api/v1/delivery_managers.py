"""Map delivery managers (tenant users) to customers; history via valid_to."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import DM_ASSIGNMENT_ROLES, get_current_user, org_role_allowed
from app.models.dimensions import DimCustomer
from app.models.phase7 import CustomerDeliveryManagerAssignment
from app.models.tenant import User
from app.schemas.delivery_manager import (
    AssignDeliveryManagerBody,
    DeliveryManagerAssignmentListResponse,
    DeliveryManagerAssignmentRow,
    TenantUserListResponse,
    TenantUserItem,
)
from app.services.access_scope import accessible_org_ids

router = APIRouter(prefix="/delivery-managers", tags=["delivery-managers"])


@router.get(
    "/tenant-users",
    response_model=TenantUserListResponse,
    summary="List active users in the tenant (for DM picker)",
)
async def list_tenant_users(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TenantUserListResponse:
    res = await session.execute(
        select(User.user_id, User.email)
        .where(User.tenant_id == user.tenant_id, User.is_active.is_(True))
        .order_by(User.email)
    )
    items = [TenantUserItem(user_id=r[0], email=r[1]) for r in res.all()]
    return TenantUserListResponse(items=items)


@router.get(
    "/assignments",
    response_model=DeliveryManagerAssignmentListResponse,
    summary="Current DM assignment per customer (valid_to is null)",
)
async def list_assignments(
    org_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DeliveryManagerAssignmentListResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )

    q = (
        select(
            CustomerDeliveryManagerAssignment.assignment_id,
            CustomerDeliveryManagerAssignment.org_id,
            CustomerDeliveryManagerAssignment.customer_id,
            DimCustomer.customer_name,
            CustomerDeliveryManagerAssignment.delivery_manager_user_id,
            User.email,
            CustomerDeliveryManagerAssignment.valid_from,
        )
        .select_from(CustomerDeliveryManagerAssignment)
        .join(DimCustomer, DimCustomer.customer_id == CustomerDeliveryManagerAssignment.customer_id)
        .join(User, User.user_id == CustomerDeliveryManagerAssignment.delivery_manager_user_id)
        .where(
            CustomerDeliveryManagerAssignment.tenant_id == user.tenant_id,
            CustomerDeliveryManagerAssignment.org_id == org_id,
            CustomerDeliveryManagerAssignment.valid_to.is_(None),
        )
        .order_by(DimCustomer.customer_name)
    )
    res = await session.execute(q)
    items = [
        DeliveryManagerAssignmentRow(
            assignment_id=r[0],
            org_id=r[1],
            customer_id=r[2],
            customer_legal=r[3],
            delivery_manager_user_id=r[4],
            delivery_manager_email=r[5],
            valid_from=r[6],
        )
        for r in res.all()
    ]
    return DeliveryManagerAssignmentListResponse(items=items)


@router.put(
    "/assignments",
    response_model=DeliveryManagerAssignmentRow,
    summary="Assign or replace the delivery manager for a customer",
)
async def assign_delivery_manager(
    body: AssignDeliveryManagerBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DeliveryManagerAssignmentRow:
    accessible = await accessible_org_ids(session, user.user_id)
    if body.org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    if not await org_role_allowed(session, user.user_id, body.org_id, DM_ASSIGNMENT_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role to assign DMs", "details": None}},
        )

    cust = await session.scalar(
        select(DimCustomer).where(
            DimCustomer.customer_id == body.customer_id,
            DimCustomer.tenant_id == user.tenant_id,
            DimCustomer.org_id == body.org_id,
        )
    )
    if cust is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Customer not in organization", "details": None}},
        )

    dm = await session.scalar(
        select(User).where(
            User.user_id == body.delivery_manager_user_id,
            User.tenant_id == user.tenant_id,
            User.is_active.is_(True),
        )
    )
    if dm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not in tenant", "details": None}},
        )

    today = date.today()
    prev = await session.scalar(
        select(CustomerDeliveryManagerAssignment).where(
            CustomerDeliveryManagerAssignment.tenant_id == user.tenant_id,
            CustomerDeliveryManagerAssignment.customer_id == body.customer_id,
            CustomerDeliveryManagerAssignment.valid_to.is_(None),
        )
    )
    if prev is not None:
        if prev.delivery_manager_user_id == body.delivery_manager_user_id:
            return DeliveryManagerAssignmentRow(
                assignment_id=prev.assignment_id,
                org_id=prev.org_id,
                customer_id=prev.customer_id,
                customer_legal=cust.customer_name,
                delivery_manager_user_id=prev.delivery_manager_user_id,
                delivery_manager_email=dm.email,
                valid_from=prev.valid_from,
            )
        prev.valid_to = today
        prev.updated_at = datetime.now(timezone.utc)

    row = CustomerDeliveryManagerAssignment(
        tenant_id=user.tenant_id,
        org_id=body.org_id,
        customer_id=body.customer_id,
        delivery_manager_user_id=body.delivery_manager_user_id,
        valid_from=today,
        valid_to=None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    return DeliveryManagerAssignmentRow(
        assignment_id=row.assignment_id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        customer_legal=cust.customer_name,
        delivery_manager_user_id=row.delivery_manager_user_id,
        delivery_manager_email=dm.email,
        valid_from=row.valid_from,
    )
