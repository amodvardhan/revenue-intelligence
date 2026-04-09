"""Create and list users in the current tenant (directory users for DM assignment, etc.)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import (
    TENANT_DIRECTORY_ADMIN_ROLES,
    get_current_user,
    org_role_allowed,
    require_tenant_directory_admin,
)
from app.core.security import hash_password
from app.models.dimensions import UserOrgRole
from app.models.tenant import User
from app.schemas.tenant_directory import (
    CreateTenantUserBody,
    CreateTenantUserResponse,
    OrgRoleItem,
    TenantUserItem,
    TenantUserListResponse,
)

router = APIRouter(prefix="/tenant", tags=["tenant"])


@router.get(
    "/users",
    response_model=TenantUserListResponse,
    summary="List users in the tenant with organization roles",
)
async def list_tenant_users(
    user: User = Depends(require_tenant_directory_admin),
    session: AsyncSession = Depends(get_db),
) -> TenantUserListResponse:
    res = await session.execute(
        select(User)
        .where(User.tenant_id == user.tenant_id)
        .options(selectinload(User.org_roles).selectinload(UserOrgRole.organization))
        .order_by(User.email)
    )
    rows = res.scalars().unique().all()
    items: list[TenantUserItem] = []
    for u in rows:
        org_roles: list[OrgRoleItem] = []
        for ur in u.org_roles:
            oname = ur.organization.org_name if ur.organization is not None else ""
            org_roles.append(OrgRoleItem(org_id=ur.org_id, org_name=oname, role=ur.role))
        items.append(
            TenantUserItem(
                user_id=u.user_id,
                email=u.email,
                is_active=u.is_active,
                org_roles=org_roles,
            )
        )
    return TenantUserListResponse(items=items)


@router.post(
    "/users",
    response_model=CreateTenantUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tenant user and assign an organization role",
)
async def create_tenant_user(
    body: CreateTenantUserBody,
    user: User = Depends(require_tenant_directory_admin),
    session: AsyncSession = Depends(get_db),
) -> CreateTenantUserResponse:
    if not await org_role_allowed(session, user.user_id, body.org_id, TENANT_DIRECTORY_ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You must be Admin or IT Admin on the target organization to add users",
                    "details": None,
                }
            },
        )

    new_user = User(
        tenant_id=user.tenant_id,
        email=body.email.strip().lower(),
        password_hash=hash_password(body.password),
        primary_auth="local",
        is_active=True,
    )
    session.add(new_user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "A user with this email already exists in the tenant",
                    "details": None,
                }
            },
        ) from None
    session.add(
        UserOrgRole(
            user_id=new_user.user_id,
            org_id=body.org_id,
            role=body.role,
        )
    )
    await session.commit()

    return CreateTenantUserResponse(user_id=new_user.user_id, email=new_user.email)
