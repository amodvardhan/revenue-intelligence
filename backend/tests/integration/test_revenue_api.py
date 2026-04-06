"""Integration tests for GET /api/v1/revenue (requires Postgres)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.dimensions import DimOrganization, UserOrgRole
from app.models.facts import FactRevenue
from app.models.tenant import Tenant, User


async def _seed_user_with_fact(session: AsyncSession) -> tuple[str, str, str]:
    """Return (access_token, org_id_str, other_org_id_str)."""
    tenant = Tenant(name="API Test Tenant")
    session.add(tenant)
    await session.flush()

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Org A")
    session.add(org)
    org_b = DimOrganization(tenant_id=tenant.tenant_id, org_name="Org B")
    session.add(org_b)
    await session.flush()

    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"test-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(user)
    await session.flush()

    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))

    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("99.9900"),
            currency_code="USD",
            revenue_date=date(2026, 3, 1),
            org_id=org.org_id,
            source_system="test",
            external_id=f"ext-{uid}-1",
            batch_id=None,
        )
    )
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("1.0000"),
            currency_code="USD",
            revenue_date=date(2026, 3, 2),
            org_id=org_b.org_id,
            source_system="test",
            external_id=f"ext-{uid}-2",
            batch_id=None,
        )
    )
    await session.flush()

    token = create_access_token(subject=str(user.user_id))
    return token, str(org.org_id), str(org_b.org_id)


@pytest.mark.asyncio
async def test_revenue_requires_auth(async_client: AsyncClient) -> None:
    r = await async_client.get("/api/v1/revenue")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_revenue_lists_accessible_orgs_only(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, org_a, _org_b = await _seed_user_with_fact(db_session)
    r = await async_client.get(
        "/api/v1/revenue",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["next_cursor"] is None
    assert len(data["items"]) == 1
    assert data["items"][0]["org_id"] == org_a
    assert data["items"][0]["amount"] == "99.9900"


@pytest.mark.asyncio
async def test_revenue_forbidden_org(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, _org_a, org_b = await _seed_user_with_fact(db_session)
    r = await async_client.get(
        "/api/v1/revenue",
        params={"org_id": org_b},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_revenue_filter_by_org_id(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, org_a, _ = await _seed_user_with_fact(db_session)
    r = await async_client.get(
        "/api/v1/revenue",
        params={"org_id": org_a},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
