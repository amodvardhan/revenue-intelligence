"""Phase 6 — governance APIs (tenant security, audit export, operations summary)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.models.audit import AuditEvent
from app.models.dimensions import DimOrganization, UserOrgRole
from app.models.facts import IngestionBatch
from app.models.hubspot_integration import HubspotConnection, IntegrationSyncRun
from app.models.phase6_governance import (
    IdpGroupRoleMapping,
    TenantEmailDomainAllowlist,
    TenantSecuritySettings,
    UserPermission,
)
from app.models.tenant import Tenant, User
from app.services.identity.federation import FederatedLoginError, provision_or_login_federated_user


async def _it_admin_setup(session: AsyncSession) -> tuple[str, str]:
    tenant = Tenant(name=f"p6-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    session.add(org)
    await session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"p6-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("secretpass12"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="it_admin"))
    session.add(
        UserPermission(
            user_id=user.user_id,
            tenant_id=tenant.tenant_id,
            permission_code="audit_export",
        )
    )
    await session.flush()
    token = create_access_token(subject=str(user.user_id))
    return token, str(tenant.tenant_id)


@pytest.mark.asyncio
async def test_tenant_security_get(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, _tid = await _it_admin_setup(db_session)
    res = await async_client.get(
        "/api/v1/tenant/security",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["reporting_currency_code"] == "USD"
    assert "invite_only" in data
    assert "sso_oidc_enabled" in data


@pytest.mark.asyncio
async def test_operations_summary(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, _tid = await _it_admin_setup(db_session)
    res = await async_client.get(
        "/api/v1/admin/operations/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "hubspot" in body
    assert "background_jobs" in body


@pytest.mark.asyncio
async def test_audit_export_csv(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, _tid = await _it_admin_setup(db_session)
    res = await async_client.post(
        "/api/v1/audit/exports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_families": ["sso_security"],
            "created_from": "2026-01-01T00:00:00Z",
            "created_to": "2026-04-06T23:59:59Z",
            "format": "csv",
        },
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_auth_me_includes_primary_auth(async_client: AsyncClient, db_session: AsyncSession) -> None:
    tenant = Tenant(name=f"p6me-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"p6me-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("x"),
    )
    db_session.add(user)
    await db_session.flush()
    token = create_access_token(subject=str(user.user_id))
    res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data.get("primary_auth") == "local"
    assert data.get("sso_required_for_user") is False


def _clear_settings_cache() -> None:
    get_settings.cache_clear()


async def _viewer_only_setup(session: AsyncSession) -> tuple[str, str]:
    tenant = Tenant(name=f"p6v-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    session.add(org)
    await session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"p6v-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("viewerpass12"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="viewer"))
    await session.flush()
    token = create_access_token(subject=str(user.user_id))
    return token, str(tenant.tenant_id)


# --- Story 6.1 — SSO / federation ---


@pytest.mark.asyncio
async def test_story_6_1_oidc_login_400_when_sso_disabled(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, tid = await _it_admin_setup(db_session)
    monkeypatch.setenv("ENABLE_SSO", "false")
    _clear_settings_cache()
    try:
        res = await async_client.get(f"/api/v1/auth/sso/oidc/login?tenant_id={tid}", follow_redirects=False)
        assert res.status_code == 400
        body = res.json()
        assert body["detail"]["error"]["code"] == "SSO_NOT_CONFIGURED"
    finally:
        monkeypatch.delenv("ENABLE_SSO", raising=False)
        _clear_settings_cache()


@pytest.mark.asyncio
async def test_story_6_1_put_sso_configuration_stores_oidc_and_no_secret_field(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, tid = await _it_admin_setup(db_session)
    res = await async_client.put(
        "/api/v1/tenant/sso/configuration",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "protocol": "oidc",
            "is_enabled": True,
            "display_name": "Corp IdP",
            "oidc_issuer": "https://idp.example.com",
            "oidc_client_id": "client-id-123",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "oidc_client_secret" not in data
    assert data["oidc"]["oidc_issuer"] == "https://idp.example.com"
    assert data["oidc_redirect_uri_readonly"].endswith("/api/v1/auth/sso/oidc/callback")


@pytest.mark.asyncio
async def test_story_6_1_domain_allowlist_api_round_trip(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, _tid = await _it_admin_setup(db_session)
    post = await async_client.post(
        "/api/v1/tenant/sso/domain-allowlist",
        headers={"Authorization": f"Bearer {token}"},
        json={"email_domain": "partner.example"},
    )
    assert post.status_code == 201
    assert post.json()["email_domain"] == "partner.example"
    got = await async_client.get(
        "/api/v1/tenant/sso/domain-allowlist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert got.status_code == 200
    domains = {i["email_domain"] for i in got.json()["items"]}
    assert "partner.example" in domains


@pytest.mark.asyncio
async def test_story_6_1_tenant_sso_admin_endpoints_forbid_viewer(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, _tid = await _viewer_only_setup(db_session)
    res = await async_client.get(
        "/api/v1/tenant/sso/configuration",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_story_6_1_oidc_callback_missing_code_returns_safe_error(async_client: AsyncClient) -> None:
    res = await async_client.get("/api/v1/auth/sso/oidc/callback", follow_redirects=False)
    assert res.status_code == 400
    body = res.json()
    assert "traceback" not in str(body).lower()
    assert body["detail"]["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_story_6_1_jit_provision_with_domain_allowlist(db_session: AsyncSession) -> None:
    tenant = Tenant(name=f"p6jit-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        TenantEmailDomainAllowlist(
            tenant_id=tenant.tenant_id,
            email_domain="allowed.example",
            created_by_user_id=None,
        )
    )
    await db_session.flush()
    user = await provision_or_login_federated_user(
        db_session,
        tenant_id=tenant.tenant_id,
        protocol="oidc",
        idp_issuer="https://idp.example",
        idp_subject="sub-jit-1",
        email="newuser@allowed.example",
        idp_groups=None,
    )
    assert user.email == "newuser@allowed.example"
    assert user.primary_auth == "oidc"
    rres = await db_session.execute(select(UserOrgRole).where(UserOrgRole.user_id == user.user_id))
    assert rres.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_story_6_1_invite_only_blocks_jit(db_session: AsyncSession) -> None:
    tenant = Tenant(name=f"p6inv-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        TenantEmailDomainAllowlist(
            tenant_id=tenant.tenant_id,
            email_domain="corp.example",
            created_by_user_id=None,
        )
    )
    db_session.add(
        TenantSecuritySettings(tenant_id=tenant.tenant_id, invite_only=True),
    )
    await db_session.flush()
    with pytest.raises(FederatedLoginError) as exc:
        await provision_or_login_federated_user(
            db_session,
            tenant_id=tenant.tenant_id,
            protocol="oidc",
            idp_issuer="https://idp.example",
            idp_subject="sub-inv",
            email="x@corp.example",
            idp_groups=None,
        )
    assert exc.value.code == "SSO_INVITE_ONLY"


@pytest.mark.asyncio
async def test_story_6_1_domain_not_on_allowlist_blocks(db_session: AsyncSession) -> None:
    tenant = Tenant(name=f"p6dom-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        TenantEmailDomainAllowlist(
            tenant_id=tenant.tenant_id,
            email_domain="other.example",
            created_by_user_id=None,
        )
    )
    await db_session.flush()
    with pytest.raises(FederatedLoginError) as exc:
        await provision_or_login_federated_user(
            db_session,
            tenant_id=tenant.tenant_id,
            protocol="oidc",
            idp_issuer="https://idp.example",
            idp_subject="sub-dom",
            email="user@notlisted.example",
            idp_groups=None,
        )
    assert exc.value.code == "SSO_DOMAIN_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_story_6_1_explicit_group_mapping_applies_app_role(db_session: AsyncSession) -> None:
    tenant = Tenant(name=f"p6grp-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        TenantEmailDomainAllowlist(
            tenant_id=tenant.tenant_id,
            email_domain="mapped.example",
            created_by_user_id=None,
        )
    )
    db_session.add(
        IdpGroupRoleMapping(
            tenant_id=tenant.tenant_id,
            idp_group_identifier="sec-it-admins",
            app_role="it_admin",
            org_id=org.org_id,
        )
    )
    await db_session.flush()
    user = await provision_or_login_federated_user(
        db_session,
        tenant_id=tenant.tenant_id,
        protocol="oidc",
        idp_issuer="https://idp.example",
        idp_subject="sub-grp",
        email="lead@mapped.example",
        idp_groups=["sec-it-admins", "other"],
    )
    rres = await db_session.execute(
        select(UserOrgRole.role).where(
            UserOrgRole.user_id == user.user_id,
            UserOrgRole.org_id == org.org_id,
        )
    )
    assert rres.scalar_one() == "it_admin"


@pytest.mark.asyncio
async def test_story_6_1_password_login_blocked_when_sso_required_for_saml_user(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant = Tenant(name=f"p6pw-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        TenantSecuritySettings(tenant_id=tenant.tenant_id, require_sso_for_standard_users=True),
    )
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"p6pw-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("localpw12345"),
        primary_auth="saml",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="viewer"))
    await db_session.flush()
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "localpw12345"},
    )
    assert res.status_code == 403
    assert "SSO" in res.json()["detail"]["error"]["message"]


@pytest.mark.asyncio
async def test_story_6_1_break_glass_admin_password_allowed_when_sso_required(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant = Tenant(name=f"p6bg-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        TenantSecuritySettings(tenant_id=tenant.tenant_id, require_sso_for_standard_users=True),
    )
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"p6bg-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("adminpw12345"),
        primary_auth="saml",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="admin"))
    await db_session.flush()
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "adminpw12345"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_story_6_1_sso_required_for_user_on_me_when_policy_enabled(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant = Tenant(name=f"p6me-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        TenantSecuritySettings(tenant_id=tenant.tenant_id, require_sso_for_standard_users=True),
    )
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"p6me-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("x"),
        primary_auth="local",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="viewer"))
    await db_session.flush()
    token = create_access_token(subject=str(user.user_id))
    res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["sso_required_for_user"] is True


# --- Story 6.2 — audit export ---


@pytest.mark.asyncio
async def test_story_6_2_audit_export_jsonl_and_all_event_families(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, _tid = await _it_admin_setup(db_session)
    res = await async_client.post(
        "/api/v1/audit/exports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_families": ["ingestion", "nl_query", "hubspot_sync", "sso_security"],
            "created_from": "2026-01-01T00:00:00Z",
            "created_to": "2026-04-06T23:59:59Z",
            "format": "jsonl",
        },
    )
    assert res.status_code == 200
    assert "ndjson" in res.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_story_6_2_audit_export_logs_completed_action(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, tid = await _it_admin_setup(db_session)
    await async_client.post(
        "/api/v1/audit/exports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_families": ["sso_security"],
            "created_from": "2026-01-01T00:00:00Z",
            "created_to": "2026-04-06T23:59:59Z",
            "format": "csv",
        },
    )
    tres = await db_session.execute(
        select(AuditEvent).where(
            AuditEvent.tenant_id == UUID(tid),
            AuditEvent.action == "audit_export.completed",
        )
    )
    assert tres.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_story_6_2_audit_export_forbidden_without_permission(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, _tid = await _viewer_only_setup(db_session)
    res = await async_client.post(
        "/api/v1/audit/exports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_families": ["ingestion"],
            "created_from": "2026-01-01T00:00:00Z",
            "created_to": "2026-04-06T23:59:59Z",
            "format": "csv",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"]["error"]["code"] == "AUDIT_EXPORT_FORBIDDEN"


@pytest.mark.asyncio
async def test_story_6_2_audit_export_invalid_date_range_422(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, _tid = await _it_admin_setup(db_session)
    res = await async_client.post(
        "/api/v1/audit/exports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_families": ["ingestion"],
            "created_from": "2026-04-06T00:00:00Z",
            "created_to": "2026-01-01T00:00:00Z",
            "format": "csv",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_story_6_2_audit_export_range_too_large_413(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, _tid = await _it_admin_setup(db_session)
    res = await async_client.post(
        "/api/v1/audit/exports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_families": ["ingestion"],
            "created_from": "2020-01-01T00:00:00Z",
            "created_to": "2026-04-06T23:59:59Z",
            "format": "csv",
        },
    )
    assert res.status_code == 413


@pytest.mark.asyncio
async def test_story_6_2_export_rows_include_user_email_for_accountability(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, tid = await _it_admin_setup(db_session)
    uid = (
        await db_session.execute(select(User).where(User.tenant_id == UUID(tid)).limit(1))
    ).scalar_one()
    db_session.add(
        AuditEvent(
            tenant_id=uid.tenant_id,
            user_id=uid.user_id,
            action="sso.login.success",
            entity_type="user",
            entity_id=uid.user_id,
            payload={"protocol": "oidc"},
        )
    )
    await db_session.flush()
    res = await async_client.post(
        "/api/v1/audit/exports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_families": ["sso_security"],
            "created_from": "2026-04-01T00:00:00Z",
            "created_to": "2026-04-30T23:59:59Z",
            "format": "csv",
        },
    )
    assert res.status_code == 200
    text = res.text
    assert uid.email in text


# --- Story 6.3 — enterprise admin ---


@pytest.mark.asyncio
async def test_story_6_3_viewer_cannot_read_tenant_security(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, _tid = await _viewer_only_setup(db_session)
    res = await async_client.get(
        "/api/v1/tenant/security",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_story_6_3_patch_tenant_security_writes_audit_event(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, tid = await _it_admin_setup(db_session)
    res = await async_client.patch(
        "/api/v1/tenant/security",
        headers={"Authorization": f"Bearer {token}"},
        json={"invite_only": True, "idle_timeout_minutes": 30},
    )
    assert res.status_code == 200
    assert res.json()["invite_only"] is True
    ev = await db_session.execute(
        select(AuditEvent).where(
            AuditEvent.tenant_id == UUID(tid),
            AuditEvent.action == "tenant.security.patch",
        )
    )
    assert ev.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_story_6_3_reporting_currency_visible_on_tenant_security(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, _tid = await _it_admin_setup(db_session)
    res = await async_client.get(
        "/api/v1/tenant/security",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["reporting_currency_code"] == "USD"


# --- Story 6.4 — operational visibility ---


@pytest.mark.asyncio
async def test_story_6_4_operations_summary_surfaces_hubspot_partial_failure(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, tid = await _it_admin_setup(db_session)
    tenant_uuid = UUID(tid)
    db_session.add(
        HubspotConnection(
            tenant_id=tenant_uuid,
            status="connected",
            last_error=None,
        )
    )
    db_session.add(
        IntegrationSyncRun(
            tenant_id=tenant_uuid,
            integration_code="hubspot",
            trigger="manual",
            status="completed_with_errors",
            started_at=datetime.now(tz=UTC),
            completed_at=datetime.now(tz=UTC),
            rows_failed=3,
            error_summary="3 deals failed validation",
        )
    )
    await db_session.flush()
    res = await async_client.get(
        "/api/v1/admin/operations/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    hub = res.json()["hubspot"]
    assert hub["last_error"] == "3 deals failed validation"


@pytest.mark.asyncio
async def test_story_6_4_operations_summary_includes_failed_batch_stub(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, tid = await _it_admin_setup(db_session)
    tenant_uuid = UUID(tid)
    db_session.add(
        IngestionBatch(
            tenant_id=tenant_uuid,
            source_system="excel",
            filename="bad.xlsx",
            status="failed",
            started_at=datetime.now(tz=UTC),
            completed_at=datetime.now(tz=UTC),
            error_log={"detail": "validation failed"},
        )
    )
    await db_session.flush()
    res = await async_client.get(
        "/api/v1/admin/operations/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    items = res.json()["background_jobs"]["items"]
    assert any(i.get("status") == "failed" for i in items)
