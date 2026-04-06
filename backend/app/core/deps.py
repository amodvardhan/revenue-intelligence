"""Shared FastAPI dependencies."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db, set_session_context
from app.core.security import decode_token
from app.models.dimensions import UserOrgRole
from app.models.tenant import User

security_scheme = HTTPBearer(auto_error=False)

INGEST_ROLES = frozenset({"finance", "admin", "it_admin"})
NL_QUERY_ROLES = frozenset({"viewer", "cxo", "bu_head", "finance", "admin", "it_admin"})
QUERY_AUDIT_ROLES = frozenset({"finance", "it_admin", "admin"})

HUBSPOT_CONNECT_ROLES = frozenset({"it_admin", "admin"})
HUBSPOT_SYNC_ROLES = frozenset({"it_admin", "admin"})
HUBSPOT_READ_ROLES = frozenset({"finance", "it_admin", "admin"})
SOURCE_RECONCILIATION_ROLES = frozenset({"finance", "it_admin", "admin"})
HUBSPOT_MAPPING_PATCH_ROLES = frozenset({"finance", "it_admin", "admin"})
HUBSPOT_CONFLICT_PATCH_ROLES = frozenset({"finance", "it_admin", "admin"})

PHASE5_UPLOAD_ROLES = frozenset({"finance", "admin", "it_admin"})
TENANT_SETTINGS_WRITE_ROLES = frozenset({"admin", "it_admin", "finance"})
SEGMENT_DEFINITION_ROLES = frozenset({"bu_head", "finance", "admin", "it_admin"})
COST_RULE_ROLES = frozenset({"finance", "admin"})

TENANT_SSO_ADMIN_ROLES = frozenset({"it_admin", "admin"})


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing bearer token", "details": None}},
        )
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": str(e), "details": None}},
        ) from e
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid token", "details": None}},
        )
    user_id = uuid.UUID(sub)
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "User not found", "details": None}},
        )
    set_session_context(tenant_id=user.tenant_id, user_id=user.user_id)
    return user


async def require_ingest_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    res = await session.execute(
        select(UserOrgRole).where(
            UserOrgRole.user_id == user.user_id,
            UserOrgRole.role.in_(INGEST_ROLES),
        )
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Insufficient role for ingestion",
                    "details": None,
                }
            },
        )
    return user


async def require_nl_query_feature_enabled() -> None:
    """Fail fast when NL is off (same flag as route; avoids misleading DB-only 403s)."""
    if not get_settings().ENABLE_NL_QUERY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Natural language query is disabled (ENABLE_NL_QUERY is false in the API process environment)",
                    "details": None,
                }
            },
        )


async def require_nl_query_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    res = await session.execute(
        select(UserOrgRole).where(
            UserOrgRole.user_id == user.user_id,
            UserOrgRole.role.in_(NL_QUERY_ROLES),
        ).limit(1)
    )
    if res.scalars().first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Your role cannot use natural language query",
                    "details": None,
                }
            },
        )
    return user


async def require_query_audit_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    res = await session.execute(
        select(UserOrgRole).where(
            UserOrgRole.user_id == user.user_id,
            UserOrgRole.role.in_(QUERY_AUDIT_ROLES),
        )
    )
    if res.scalars().first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Insufficient role for query audit",
                    "details": None,
                }
            },
        )
    return user


async def _any_org_role(session: AsyncSession, user_id: uuid.UUID, allowed: frozenset[str]) -> bool:
    res = await session.execute(
        select(UserOrgRole).where(
            UserOrgRole.user_id == user_id,
            UserOrgRole.role.in_(allowed),
        )
    )
    return res.scalars().first() is not None


async def require_hubspot_enabled() -> None:
    if not get_settings().ENABLE_HUBSPOT:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "HubSpot integration is disabled",
                    "details": None,
                }
            },
        )


async def require_hubspot_connect_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not await _any_org_role(session, user.user_id, HUBSPOT_CONNECT_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "IT Admin role required", "details": None}},
        )
    return user


async def require_hubspot_sync_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not await _any_org_role(session, user.user_id, HUBSPOT_SYNC_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role for sync", "details": None}},
        )
    return user


async def require_hubspot_read_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not await _any_org_role(session, user.user_id, HUBSPOT_READ_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role", "details": None}},
        )
    return user


async def require_source_reconciliation_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not await _any_org_role(session, user.user_id, SOURCE_RECONCILIATION_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role", "details": None}},
        )
    return user


async def require_mapping_patch_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not await _any_org_role(session, user.user_id, HUBSPOT_MAPPING_PATCH_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role", "details": None}},
        )
    return user


async def require_conflict_patch_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not await _any_org_role(session, user.user_id, HUBSPOT_CONFLICT_PATCH_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role", "details": None}},
        )
    return user


async def require_phase5_enabled() -> None:
    if not get_settings().ENABLE_PHASE5:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Phase 5 features are disabled",
                    "details": None,
                }
            },
        )


async def require_phase5_upload_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    await require_phase5_enabled()
    if not await _any_org_role(session, user.user_id, PHASE5_UPLOAD_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role", "details": None}},
        )
    return user


async def require_tenant_settings_write_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    await require_phase5_enabled()
    if not await _any_org_role(session, user.user_id, TENANT_SETTINGS_WRITE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role", "details": None}},
        )
    return user


async def require_segment_definition_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    await require_phase5_enabled()
    if not await _any_org_role(session, user.user_id, SEGMENT_DEFINITION_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role", "details": None}},
        )
    return user


async def require_cost_allocation_role(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    await require_phase5_enabled()
    if not await _any_org_role(session, user.user_id, COST_RULE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role", "details": None}},
        )
    return user


async def require_tenant_sso_admin(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not await _any_org_role(session, user.user_id, TENANT_SSO_ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "IT Admin access required", "details": None}},
        )
    return user


async def require_audit_export_permission(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    from app.services.identity.federation import user_has_audit_export

    if not await user_has_audit_export(session, user.user_id, user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "AUDIT_EXPORT_FORBIDDEN",
                    "message": "Audit export permission required",
                    "details": None,
                }
            },
        )
    return user
