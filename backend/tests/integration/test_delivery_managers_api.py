"""Integration tests for delivery manager assignments."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config as config_module
from app.core.security import create_access_token, hash_password
from app.models.dimensions import DimCustomer, DimOrganization, UserOrgRole
from app.models.facts import FactRevenue
from app.models.tenant import Tenant, User


async def _seed_two_users_org_customer(session: AsyncSession) -> tuple[str, str, str, str]:
    """token, org_id, customer_id, dm_user_id (second user)."""
    tenant = Tenant(name="DM Test Tenant")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="DM Org")
    session.add(org)
    await session.flush()
    cust = DimCustomer(
        tenant_id=tenant.tenant_id,
        customer_name="Globex",
        org_id=org.org_id,
    )
    session.add(cust)
    await session.flush()

    uid = uuid4().hex[:12]
    admin = User(
        tenant_id=tenant.tenant_id,
        email=f"admin-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    dm = User(
        tenant_id=tenant.tenant_id,
        email=f"dm-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add_all([admin, dm])
    await session.flush()
    session.add(UserOrgRole(user_id=admin.user_id, org_id=org.org_id, role="finance"))
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("10.0000"),
            currency_code="USD",
            revenue_date=date(2026, 1, 1),
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="test",
            external_id=f"dm-{uid}-f",
            batch_id=None,
        )
    )
    await session.flush()
    token = create_access_token(subject=str(admin.user_id))
    return token, str(org.org_id), str(cust.customer_id), str(dm.user_id)


@pytest.mark.asyncio
async def test_assign_and_list_delivery_manager(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENABLE_PHASE7", "true")
    config_module.get_settings.cache_clear()
    try:
        token, org_id, customer_id, dm_id = await _seed_two_users_org_customer(db_session)

        r = await async_client.put(
            "/api/v1/delivery-managers/assignments",
            headers={"Authorization": f"Bearer {token}"},
            json={"org_id": org_id, "customer_id": customer_id, "delivery_manager_user_id": dm_id},
        )
        assert r.status_code == 200
        row = r.json()
        assert row["delivery_manager_user_id"] == dm_id
        assert row["customer_id"] == customer_id

        r2 = await async_client.get(
            "/api/v1/delivery-managers/assignments",
            params={"org_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert len(items) == 1
        assert items[0]["delivery_manager_email"].startswith("dm-")
    finally:
        config_module.get_settings.cache_clear()
