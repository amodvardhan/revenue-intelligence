"""Variance narratives on matrix delta rows and DM prompt list."""

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
from app.models.phase7 import CustomerDeliveryManagerAssignment
from app.models.tenant import Tenant, User


@pytest.mark.asyncio
async def test_variance_comment_round_trip_and_prompts(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENABLE_PHASE7", "true")
    config_module.get_settings.cache_clear()
    try:
        tenant = Tenant(name="Var Narr Tenant")
        db_session.add(tenant)
        await db_session.flush()
        org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Var Narr Org")
        db_session.add(org)
        await db_session.flush()
        cust = DimCustomer(
            tenant_id=tenant.tenant_id,
            customer_name="Northwind Legal",
            customer_name_common="Northwind",
            org_id=org.org_id,
        )
        db_session.add(cust)
        await db_session.flush()
        uid = uuid4().hex[:12]
        dm = User(
            tenant_id=tenant.tenant_id,
            email=f"dm-var-{uid}@example.com",
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
                amount=Decimal("100.0000"),
                currency_code="USD",
                revenue_date=date(2026, 1, 1),
                org_id=org.org_id,
                customer_id=cust.customer_id,
                source_system="excel",
                external_id=f"var-{uid}-1",
                batch_id=None,
            )
        )
        db_session.add(
            FactRevenue(
                tenant_id=tenant.tenant_id,
                amount=Decimal("130.0000"),
                currency_code="USD",
                revenue_date=date(2026, 2, 1),
                org_id=org.org_id,
                customer_id=cust.customer_id,
                source_system="excel",
                external_id=f"var-{uid}-2",
                batch_id=None,
            )
        )
        await db_session.flush()
        token = create_access_token(subject=str(dm.user_id))
        org_id = str(org.org_id)
        cust_id = str(cust.customer_id)

        pr = await async_client.get(
            "/api/v1/revenue/variance-comment-prompts",
            params={"org_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pr.status_code == 200
        prompts_before = pr.json()["items"]
        assert len(prompts_before) >= 1
        assert prompts_before[0]["customer_id"] == cust_id

        r0 = await async_client.get(
            "/api/v1/revenue/matrix",
            params={"org_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r0.status_code == 200
        data0 = r0.json()
        feb_key = data0["month_columns"][1]["key"]
        delta_line = next(l for l in data0["lines"] if l["row_type"] == "delta")
        assert delta_line["customer_id"] == cust_id
        assert delta_line["variance_comments"][1] is None

        wr = await async_client.put(
            "/api/v1/revenue/matrix/variance-comment",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_id": org_id,
                "customer_id": cust_id,
                "revenue_month": feb_key,
                "comment_text": "Milestone billing in February.",
            },
        )
        assert wr.status_code == 200
        data1 = wr.json()
        delta_after = next(l for l in data1["lines"] if l["row_type"] == "delta")
        assert delta_after["variance_comments"][1] == "Milestone billing in February."

        pr2 = await async_client.get(
            "/api/v1/revenue/variance-comment-prompts",
            params={"org_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pr2.status_code == 200
        assert pr2.json()["items"] == []

        clr = await async_client.put(
            "/api/v1/revenue/matrix/variance-comment",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_id": org_id,
                "customer_id": cust_id,
                "revenue_month": feb_key,
                "comment_text": "",
            },
        )
        assert clr.status_code == 200
        data2 = clr.json()
        delta_cleared = next(l for l in data2["lines"] if l["row_type"] == "delta")
        assert delta_cleared["variance_comments"][1] is None
    finally:
        config_module.get_settings.cache_clear()
