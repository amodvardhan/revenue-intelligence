"""Integration tests for dim_project API."""

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


async def _seed_finance(session: AsyncSession) -> tuple[str, str, str]:
    """token, org_id, customer_id"""
    tenant = Tenant(name="Proj Tenant")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Proj Org")
    session.add(org)
    await session.flush()
    cust = DimCustomer(tenant_id=tenant.tenant_id, customer_name="Acme", org_id=org.org_id)
    session.add(cust)
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
            amount=Decimal("10"),
            currency_code="USD",
            revenue_date=date(2026, 1, 1),
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="p",
            external_id=f"p-{uid}",
            batch_id=None,
        )
    )
    await session.flush()
    token = create_access_token(subject=str(u.user_id))
    return token, str(org.org_id), str(cust.customer_id)


@pytest.mark.asyncio
async def test_projects_list_and_create(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id, cust_id = await _seed_finance(db_session)
    r = await async_client.get(
        "/api/v1/projects",
        params={"org_id": org_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["items"] == []

    r2 = await async_client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"org_id": org_id, "project_name": "Rollout Q1", "customer_id": cust_id},
    )
    assert r2.status_code == 201
    assert r2.json()["project_name"] == "Rollout Q1"

    r3 = await async_client.get(
        "/api/v1/projects",
        params={"org_id": org_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(r3.json()["items"]) == 1
