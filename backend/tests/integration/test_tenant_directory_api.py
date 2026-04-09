"""Integration tests for tenant user directory (admin-only)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.dimensions import DimCustomer, DimOrganization, UserOrgRole
from app.models.facts import FactRevenue
from app.models.tenant import Tenant, User


async def _seed_admin(session: AsyncSession) -> tuple[str, str]:
    tenant = Tenant(name="Dir Tenant")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Dir Org")
    session.add(org)
    await session.flush()
    uid = uuid4().hex[:12]
    admin = User(
        tenant_id=tenant.tenant_id,
        email=f"adm-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(admin)
    await session.flush()
    session.add(UserOrgRole(user_id=admin.user_id, org_id=org.org_id, role="admin"))
    cust = DimCustomer(tenant_id=tenant.tenant_id, customer_name="C", org_id=org.org_id)
    session.add(cust)
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("1"),
            currency_code="USD",
            revenue_date=date(2026, 1, 1),
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="t",
            external_id=f"t-{uid}",
            batch_id=None,
        )
    )
    await session.flush()
    token = create_access_token(subject=str(admin.user_id))
    return token, str(org.org_id)


async def _seed_viewer(session: AsyncSession) -> str:
    tenant = Tenant(name="View Tenant")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="View Org")
    session.add(org)
    await session.flush()
    uid = uuid4().hex[:12]
    u = User(
        tenant_id=tenant.tenant_id,
        email=f"view-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(u)
    await session.flush()
    session.add(UserOrgRole(user_id=u.user_id, org_id=org.org_id, role="viewer"))
    await session.flush()
    return create_access_token(subject=str(u.user_id))


@pytest.mark.asyncio
async def test_tenant_users_forbidden_for_viewer(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token = await _seed_viewer(db_session)
    r = await async_client.get("/api/v1/tenant/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_tenant_users_list_and_create(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_admin(db_session)
    r = await async_client.get("/api/v1/tenant/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1

    nu = f"new-{uuid4().hex[:8]}@example.com"
    r2 = await async_client.post(
        "/api/v1/tenant/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": nu, "password": "password88", "org_id": org_id, "role": "finance"},
    )
    assert r2.status_code == 201
    r3 = await async_client.get("/api/v1/tenant/users", headers={"Authorization": f"Bearer {token}"})
    assert len(r3.json()["items"]) == 2
    emails = {x["email"] for x in r3.json()["items"]}
    assert nu in emails


@pytest.mark.asyncio
async def test_tenant_users_duplicate_email(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_admin(db_session)
    nu = f"dup-{uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/tenant/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": nu, "password": "password88", "org_id": org_id, "role": "viewer"},
    )
    r = await async_client.post(
        "/api/v1/tenant/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": nu, "password": "password99", "org_id": org_id, "role": "viewer"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_tenant_users_create_account_manager_and_delivery_manager_roles(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, org_id = await _seed_admin(db_session)
    for role in ("account_manager", "delivery_manager"):
        email = f"{role}-{uuid4().hex[:8]}@example.com"
        r = await async_client.post(
            "/api/v1/tenant/users",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": email, "password": "password88", "org_id": org_id, "role": role},
        )
        assert r.status_code == 201, r.text
