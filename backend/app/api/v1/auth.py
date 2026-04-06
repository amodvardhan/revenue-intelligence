"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.dimensions import DimOrganization, UserOrgRole
from app.services.identity.federation import get_security_settings
from app.services.access_scope import business_unit_scope
from app.models.tenant import Tenant, User
from app.schemas.auth import (
    BusinessUnitScope,
    LoginRequest,
    MeResponse,
    MeRole,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _ensure_user_org_role_if_missing(session: AsyncSession, user: User) -> None:
    """Assign a default org role when the user has none (data repair; registration already sets admin)."""
    existing = await session.execute(
        select(UserOrgRole.user_id).where(UserOrgRole.user_id == user.user_id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return
    org_res = await session.execute(
        select(DimOrganization.org_id).where(DimOrganization.tenant_id == user.tenant_id).limit(1)
    )
    org_id = org_res.scalar_one_or_none()
    if org_id is None:
        return
    n_users = await session.execute(
        select(func.count()).select_from(User).where(User.tenant_id == user.tenant_id)
    )
    n = int(n_users.scalar_one() or 0)
    role = "admin" if n == 1 else "viewer"
    session.add(UserOrgRole(user_id=user.user_id, org_id=org_id, role=role))
    await session.flush()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register user and tenant",
    description="Creates a tenant, root organization, user, and admin role. Restrict in production.",
)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Registration disabled", "details": None}},
        )
    tenant = Tenant(name=body.tenant_name)
    session.add(tenant)
    await session.flush()

    org = DimOrganization(
        tenant_id=tenant.tenant_id,
        org_name=body.tenant_name,
        parent_org_id=None,
    )
    session.add(org)
    await session.flush()

    user = User(
        tenant_id=tenant.tenant_id,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.flush()

    session.add(
        UserOrgRole(
            user_id=user.user_id,
            org_id=org.org_id,
            role="admin",
        )
    )
    await session.commit()

    token = create_access_token(subject=str(user.user_id), extra_claims={"tenant_id": str(tenant.tenant_id)})
    return TokenResponse(
        user_id=user.user_id,
        tenant_id=tenant.tenant_id,
        email=user.email,
        access_token=token,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Exchange email/password for a JWT access token.",
)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid credentials", "details": None}},
        )
    await _ensure_user_org_role_if_missing(session, user)
    sec = await get_security_settings(session, user.tenant_id)
    roles_res = await session.execute(select(UserOrgRole.role).where(UserOrgRole.user_id == user.user_id))
    roles = {r for r in roles_res.scalars().all()}
    if sec.require_sso_for_standard_users and user.primary_auth in ("oidc", "saml"):
        is_break_glass = "admin" in roles and user.password_hash is not None
        if not is_break_glass:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "Password sign-in disabled for this account — use SSO",
                        "details": None,
                    }
                },
            )
    token = create_access_token(subject=str(user.user_id), extra_claims={"tenant_id": str(user.tenant_id)})
    return TokenResponse(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        email=user.email,
        access_token=token,
    )


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Current user profile",
)
async def me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)) -> MeResponse:
    res = await session.execute(select(UserOrgRole).where(UserOrgRole.user_id == user.user_id))
    role_rows = res.scalars().all()
    roles = [MeRole(org_id=r.org_id, role=r.role) for r in role_rows]
    mode, bu_ids = await business_unit_scope(session, user.user_id)
    sec = await get_security_settings(session, user.tenant_id)
    role_names = {r.role for r in role_rows}
    is_break_glass = "admin" in role_names and user.password_hash is not None
    sso_required_for_user = bool(sec.require_sso_for_standard_users and not is_break_glass)
    return MeResponse(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        email=user.email,
        roles=roles,
        business_unit_scope=BusinessUnitScope(mode=mode, business_unit_ids=bu_ids),
        primary_auth=user.primary_auth,
        sso_required_for_user=sso_required_for_user,
    )
