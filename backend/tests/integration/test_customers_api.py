"""Integration tests for /api/v1/customers."""

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


async def _seed_finance(session: AsyncSession) -> tuple[str, str]:
    tenant = Tenant(name="Cust API Tenant")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Cust Org")
    session.add(org)
    await session.flush()
    uid = uuid4().hex[:12]
    u = User(
        tenant_id=tenant.tenant_id,
        email=f"fin-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(u)
    await session.flush()
    session.add(UserOrgRole(user_id=u.user_id, org_id=org.org_id, role="finance"))
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("1"),
            currency_code="USD",
            revenue_date=date(2026, 1, 1),
            org_id=org.org_id,
            customer_id=None,
            source_system="c",
            external_id=f"c-{uid}",
            batch_id=None,
        )
    )
    await session.flush()
    token = create_access_token(subject=str(u.user_id))
    return token, str(org.org_id)


@pytest.mark.asyncio
async def test_customers_list_empty_then_create(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_finance(db_session)
    r = await async_client.get(
        "/api/v1/customers",
        params={"org_id": org_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["items"] == []

    r2 = await async_client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "org_id": org_id,
            "customer_name": "Globex Corp",
            "customer_name_common": "Globex",
            "customer_code": "GLX-01",
        },
    )
    assert r2.status_code == 201
    assert r2.json()["customer_name"] == "Globex Corp"

    r3 = await async_client.get(
        "/api/v1/customers",
        params={"org_id": org_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(r3.json()["items"]) == 1


@pytest.mark.asyncio
async def test_customers_duplicate_code(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_finance(db_session)
    code = f"CODE-{uuid4().hex[:6]}"
    await async_client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={"org_id": org_id, "customer_name": "A", "customer_code": code},
    )
    r = await async_client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={"org_id": org_id, "customer_name": "B", "customer_code": code},
    )
    assert r.status_code == 409
