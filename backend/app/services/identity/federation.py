"""JIT provisioning, federated identity rows, optional IdP group → role mapping."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.dimensions import DimOrganization, UserOrgRole
from app.models.phase6_governance import (
    IdpGroupRoleMapping,
    TenantEmailDomainAllowlist,
    TenantSecuritySettings,
    UserFederatedIdentity,
    UserPermission,
)
from app.models.tenant import User

logger = logging.getLogger(__name__)


class FederatedLoginError(Exception):
    """Business codes: SSO_INVITE_ONLY, SSO_DOMAIN_NOT_ALLOWED, USER_INACTIVE."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def get_security_settings(session: AsyncSession, tenant_id: uuid.UUID) -> TenantSecuritySettings:
    res = await session.execute(
        select(TenantSecuritySettings).where(TenantSecuritySettings.tenant_id == tenant_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = TenantSecuritySettings(tenant_id=tenant_id)
        session.add(row)
        await session.flush()
    return row


def _email_domain(email: str) -> str:
    parts = email.strip().lower().split("@", 1)
    if len(parts) != 2 or not parts[1]:
        raise ValueError("Invalid email")
    return parts[1]


async def _domain_allowed(session: AsyncSession, tenant_id: uuid.UUID, email: str) -> bool:
    domain = _email_domain(email)
    res = await session.execute(
        select(TenantEmailDomainAllowlist).where(
            TenantEmailDomainAllowlist.tenant_id == tenant_id,
            TenantEmailDomainAllowlist.email_domain == domain,
        )
    )
    return res.scalar_one_or_none() is not None


async def _first_org_id(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID | None:
    res = await session.execute(
        select(DimOrganization.org_id).where(DimOrganization.tenant_id == tenant_id).limit(1)
    )
    return res.scalar_one_or_none()


async def _append_audit(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )
    )


async def provision_or_login_federated_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    protocol: str,
    idp_issuer: str,
    idp_subject: str,
    email: str,
    idp_groups: list[str] | None,
) -> User:
    """Return active user; creates or links federated identity per tenant policy."""
    email_norm = email.strip().lower()
    sec = await get_security_settings(session, tenant_id)

    fed = await session.execute(
        select(UserFederatedIdentity).where(
            UserFederatedIdentity.tenant_id == tenant_id,
            UserFederatedIdentity.idp_issuer == idp_issuer,
            UserFederatedIdentity.idp_subject == idp_subject,
        )
    )
    existing_fed = fed.scalar_one_or_none()
    if existing_fed is not None:
        ures = await session.execute(select(User).where(User.user_id == existing_fed.user_id))
        user = ures.scalar_one()
        if not user.is_active:
            await _append_audit(
                session,
                tenant_id=tenant_id,
                user_id=user.user_id,
                action="sso.login.denied",
                entity_type="user",
                entity_id=user.user_id,
                payload={"reason": "inactive"},
            )
            raise FederatedLoginError("USER_INACTIVE")
        existing_fed.last_login_at = datetime.now(tz=UTC)
        user.primary_auth = protocol
        await _apply_group_mappings(session, tenant_id=tenant_id, user=user, idp_groups=idp_groups)
        await _append_audit(
            session,
            tenant_id=tenant_id,
            user_id=user.user_id,
            action="sso.login.success",
            entity_type="user",
            entity_id=user.user_id,
            payload={"protocol": protocol},
        )
        return user

    ures = await session.execute(
        select(User).where(User.tenant_id == tenant_id, User.email == email_norm)
    )
    existing_user = ures.scalar_one_or_none()
    if existing_user is not None:
        session.add(
            UserFederatedIdentity(
                user_id=existing_user.user_id,
                tenant_id=tenant_id,
                protocol=protocol,
                idp_issuer=idp_issuer,
                idp_subject=idp_subject,
                email_at_link=email_norm,
                last_login_at=datetime.now(tz=UTC),
            )
        )
        existing_user.primary_auth = protocol
        await _apply_group_mappings(session, tenant_id=tenant_id, user=existing_user, idp_groups=idp_groups)
        await _append_audit(
            session,
            tenant_id=tenant_id,
            user_id=existing_user.user_id,
            action="sso.login.success",
            entity_type="user",
            entity_id=existing_user.user_id,
            payload={"protocol": protocol, "linked": True},
        )
        return existing_user

    if sec.invite_only:
        await _append_audit(
            session,
            tenant_id=tenant_id,
            user_id=None,
            action="sso.login.denied",
            entity_type="tenant",
            entity_id=tenant_id,
            payload={"reason": "invite_only"},
        )
        raise FederatedLoginError("SSO_INVITE_ONLY")

    if not await _domain_allowed(session, tenant_id, email_norm):
        await _append_audit(
            session,
            tenant_id=tenant_id,
            user_id=None,
            action="sso.login.denied",
            entity_type="tenant",
            entity_id=tenant_id,
            payload={"reason": "domain_not_allowed", "email": email_norm},
        )
        raise FederatedLoginError("SSO_DOMAIN_NOT_ALLOWED")

    org_id = await _first_org_id(session, tenant_id)
    if org_id is None:
        logger.error("No organization for tenant %s — cannot JIT user", tenant_id)
        raise RuntimeError("Tenant has no organization")

    new_user = User(
        tenant_id=tenant_id,
        email=email_norm,
        password_hash=None,
        primary_auth=protocol,
        is_active=True,
    )
    session.add(new_user)
    await session.flush()

    session.add(
        UserOrgRole(
            user_id=new_user.user_id,
            org_id=org_id,
            role="viewer",
        )
    )
    session.add(
        UserFederatedIdentity(
            user_id=new_user.user_id,
            tenant_id=tenant_id,
            protocol=protocol,
            idp_issuer=idp_issuer,
            idp_subject=idp_subject,
            email_at_link=email_norm,
            last_login_at=datetime.now(tz=UTC),
        )
    )
    await _apply_group_mappings(session, tenant_id=tenant_id, user=new_user, idp_groups=idp_groups)
    await _append_audit(
        session,
        tenant_id=tenant_id,
        user_id=new_user.user_id,
        action="sso.login.success",
        entity_type="user",
        entity_id=new_user.user_id,
        payload={"protocol": protocol, "jit": True},
    )
    return new_user


async def _apply_group_mappings(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user: User,
    idp_groups: list[str] | None,
) -> None:
    if not idp_groups:
        return
    group_set = {g.strip() for g in idp_groups if g and str(g).strip()}
    if not group_set:
        return
    res = await session.execute(
        select(IdpGroupRoleMapping).where(IdpGroupRoleMapping.tenant_id == tenant_id)
    )
    mappings = res.scalars().all()
    for m in mappings:
        if m.idp_group_identifier not in group_set:
            continue
        existing = await session.execute(
            select(UserOrgRole).where(
                UserOrgRole.user_id == user.user_id,
                UserOrgRole.org_id == m.org_id,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            session.add(
                UserOrgRole(user_id=user.user_id, org_id=m.org_id, role=m.app_role),
            )
        else:
            row.role = m.app_role


async def user_has_audit_export(session: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
    res = await session.execute(
        select(UserPermission).where(
            UserPermission.user_id == user_id,
            UserPermission.tenant_id == tenant_id,
            UserPermission.permission_code == "audit_export",
        )
    )
    return res.scalar_one_or_none() is not None
