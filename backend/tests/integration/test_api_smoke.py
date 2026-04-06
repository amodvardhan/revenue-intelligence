"""Light coverage for health, auth profile, and ingest batch detail (404)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.dimensions import DimOrganization, UserOrgRole
from app.models.tenant import Tenant, User


async def _tenant_user_token(session: AsyncSession) -> tuple[str, str]:
    tenant = Tenant(name=f"smoke-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"smoke-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("x"),
    )
    session.add(user)
    await session.flush()
    return create_access_token(subject=str(user.user_id)), str(user.user_id)


@pytest.mark.asyncio
async def test_health_returns_ok(async_client: AsyncClient) -> None:
    res = await async_client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.asyncio
async def test_auth_me_returns_profile(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, _uid = await _tenant_user_token(db_session)
    res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "email" in data
    assert "roles" in data
    assert data["roles"] == []
    assert data["business_unit_scope"]["mode"] == "org_wide"
    assert data["business_unit_scope"]["business_unit_ids"] == []


@pytest.mark.asyncio
async def test_auth_me_includes_org_roles(async_client: AsyncClient, db_session: AsyncSession) -> None:
    tenant = Tenant(name=f"smoke2-{uuid4().hex[:8]}")
    session = db_session
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    session.add(org)
    await session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"smoke2-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("x"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="viewer"))
    await session.flush()
    token = create_access_token(subject=str(user.user_id))

    res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    roles = res.json()["roles"]
    assert len(roles) == 1
    assert roles[0]["role"] == "viewer"


@pytest.mark.asyncio
async def test_get_batch_detail_404_for_random_id(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, _ = await _tenant_user_token(db_session)
    fake_id = "00000000-0000-4000-8000-000000000001"
    res = await async_client.get(
        f"/api/v1/ingest/batches/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert res.json()["detail"]["error"]["code"] == "NOT_FOUND"
