"""Delivery managers may edit org-scoped manual matrix cells for assigned customers only."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config as config_module
from app.core.security import create_access_token, hash_password
from app.models.dimensions import DimBusinessUnit, DimCustomer, DimOrganization, UserOrgRole
from app.models.facts import FactRevenue
from app.models.phase7 import CustomerDeliveryManagerAssignment
from app.models.tenant import Tenant, User


async def _seed_dm_can_edit_matrix(session: AsyncSession) -> tuple[str, str, str]:
    """DM token, org_id, customer_id — DM has viewer on org and active assignment."""
    tenant = Tenant(name="DM Matrix Tenant")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="DM Matrix Org")
    session.add(org)
    await session.flush()
    cust = DimCustomer(
        tenant_id=tenant.tenant_id,
        customer_name="Contoso Legal",
        customer_name_common="Contoso",
        org_id=org.org_id,
    )
    session.add(cust)
    await session.flush()
    uid = uuid4().hex[:12]
    dm = User(
        tenant_id=tenant.tenant_id,
        email=f"dm-mx-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(dm)
    await session.flush()
    session.add(UserOrgRole(user_id=dm.user_id, org_id=org.org_id, role="viewer"))
    session.add(
        CustomerDeliveryManagerAssignment(
            tenant_id=tenant.tenant_id,
            org_id=org.org_id,
            customer_id=cust.customer_id,
            delivery_manager_user_id=dm.user_id,
            valid_from=date(2026, 1, 1),
            valid_to=None,
        )
    )
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("50.0000"),
            currency_code="USD",
            revenue_date=date(2026, 1, 1),
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="excel",
            external_id=f"dmx-{uid}-1",
            batch_id=None,
        )
    )
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("60.0000"),
            currency_code="USD",
            revenue_date=date(2026, 2, 1),
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="excel",
            external_id=f"dmx-{uid}-2",
            batch_id=None,
        )
    )
    await session.flush()
    token = create_access_token(subject=str(dm.user_id))
    return token, str(org.org_id), str(cust.customer_id)


@pytest.mark.asyncio
async def test_dm_assigned_customer_matrix_editable_and_put_ok(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENABLE_PHASE7", "true")
    config_module.get_settings.cache_clear()
    try:
        token, org_id, cust_id = await _seed_dm_can_edit_matrix(db_session)
        r0 = await async_client.get(
            "/api/v1/revenue/matrix",
            params={"org_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r0.status_code == 200
        data0 = r0.json()
        assert data0["lines"][0]["amounts_editable"] is True
        month_key = data0["month_columns"][1]["key"]
        rev_month = datetime.fromisoformat(month_key).date()

        r = await async_client.put(
            "/api/v1/revenue/matrix/cell",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_id": org_id,
                "customer_id": cust_id,
                "revenue_month": rev_month.isoformat(),
                "amount": "99.0000",
            },
        )
        assert r.status_code == 200
        assert r.json()["lines"][0]["amounts"] == ["50.0000", "99.0000"]
    finally:
        config_module.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_dm_cannot_write_bu_scoped_manual_cell(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENABLE_PHASE7", "true")
    config_module.get_settings.cache_clear()
    try:
        tenant = Tenant(name="DM BU Tenant")
        db_session.add(tenant)
        await db_session.flush()
        org = DimOrganization(tenant_id=tenant.tenant_id, org_name="DM BU Org")
        db_session.add(org)
        await db_session.flush()
        bu = DimBusinessUnit(tenant_id=tenant.tenant_id, org_id=org.org_id, business_unit_name="BU1")
        db_session.add(bu)
        await db_session.flush()
        cust = DimCustomer(
            tenant_id=tenant.tenant_id,
            customer_name="Fabrikam",
            org_id=org.org_id,
        )
        db_session.add(cust)
        await db_session.flush()
        uid = uuid4().hex[:12]
        dm = User(
            tenant_id=tenant.tenant_id,
            email=f"dmbu-{uid}@example.com",
            password_hash=hash_password("secret"),
        )
        db_session.add(dm)
        await db_session.flush()
        db_session.add(UserOrgRole(user_id=dm.user_id, org_id=org.org_id, role="viewer"))
        db_session.add(
            CustomerDeliveryManagerAssignment(
                tenant_id=tenant.tenant_id,
                org_id=org.org_id,
                customer_id=cust.customer_id,
                delivery_manager_user_id=dm.user_id,
                valid_from=date(2026, 1, 1),
                valid_to=None,
            )
        )
        db_session.add(
            FactRevenue(
                tenant_id=tenant.tenant_id,
                amount=Decimal("10.0000"),
                currency_code="USD",
                revenue_date=date(2026, 1, 1),
                org_id=org.org_id,
                business_unit_id=bu.business_unit_id,
                customer_id=cust.customer_id,
                source_system="excel",
                external_id=f"dmbu-{uid}-1",
                batch_id=None,
            )
        )
        await db_session.flush()
        token = create_access_token(subject=str(dm.user_id))
        org_id_s = str(org.org_id)
        cust_id_s = str(cust.customer_id)
        bu_id_s = str(bu.business_unit_id)

        r = await async_client.put(
            "/api/v1/revenue/matrix/cell",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_id": org_id_s,
                "customer_id": cust_id_s,
                "revenue_month": "2026-01-01",
                "amount": "25.0000",
                "business_unit_id": bu_id_s,
                "division_id": None,
            },
        )
        assert r.status_code == 403
    finally:
        config_module.get_settings.cache_clear()
