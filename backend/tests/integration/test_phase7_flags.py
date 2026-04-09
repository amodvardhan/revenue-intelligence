"""Phase 7 feature flag — matrix and delivery-manager APIs return 503 when disabled."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config as config_module
from app.core.security import create_access_token, hash_password
from app.models.tenant import Tenant, User


@pytest.mark.asyncio
async def test_revenue_matrix_503_when_phase7_disabled(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = Tenant(name=f"p7-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"p7-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("x"),
    )
    db_session.add(user)
    await db_session.flush()
    token = create_access_token(subject=str(user.user_id))

    monkeypatch.setenv("ENABLE_PHASE7", "false")
    config_module.get_settings.cache_clear()
    try:
        r = await async_client.get(
            "/api/v1/revenue/matrix",
            params={"org_id": str(uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 503
        body = r.json()
        err = body.get("error") or (body.get("detail") or {}).get("error")
        assert err and err.get("code") == "SERVICE_UNAVAILABLE"
    finally:
        config_module.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_delivery_managers_503_when_phase7_disabled(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = Tenant(name=f"p7dm-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"p7dm-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("x"),
    )
    db_session.add(user)
    await db_session.flush()
    token = create_access_token(subject=str(user.user_id))

    monkeypatch.setenv("ENABLE_PHASE7", "false")
    config_module.get_settings.cache_clear()
    try:
        r = await async_client.get(
            "/api/v1/delivery-managers/tenant-users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 503
        body = r.json()
        err = body.get("error") or (body.get("detail") or {}).get("error")
        assert err and err.get("code") == "SERVICE_UNAVAILABLE"
    finally:
        config_module.get_settings.cache_clear()
