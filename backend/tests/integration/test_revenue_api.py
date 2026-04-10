"""Integration tests for GET /api/v1/revenue (requires Postgres)."""

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


async def _seed_user_customer_matrix(session: AsyncSession) -> tuple[str, str]:
    """Tenant with one org, one customer, two month facts."""
    tenant = Tenant(name="Matrix Tenant")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Matrix Org")
    session.add(org)
    await session.flush()
    cust = DimCustomer(
        tenant_id=tenant.tenant_id,
        customer_name="Acme Legal",
        customer_name_common="Acme",
        org_id=org.org_id,
    )
    session.add(cust)
    await session.flush()
    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"matrix-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("100.0000"),
            currency_code="USD",
            revenue_date=date(2026, 1, 1),
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="excel",
            external_id=f"mx-{uid}-1",
            batch_id=None,
        )
    )
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("130.0000"),
            currency_code="USD",
            revenue_date=date(2026, 2, 1),
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="excel",
            external_id=f"mx-{uid}-2",
            batch_id=None,
        )
    )
    await session.flush()
    token = create_access_token(subject=str(user.user_id))
    return token, str(org.org_id)


async def _seed_matrix_customer_home_bu(session: AsyncSession) -> tuple[str, str, str]:
    """Org + BU; customer assigned to BU; fact has customer but null business_unit_id."""
    tenant = Tenant(name="Matrix BU Home Tenant")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="e-Zest Digital Solution")
    session.add(org)
    await session.flush()
    bu = DimBusinessUnit(tenant_id=tenant.tenant_id, org_id=org.org_id, business_unit_name="IO")
    session.add(bu)
    await session.flush()
    cust = DimCustomer(
        tenant_id=tenant.tenant_id,
        org_id=org.org_id,
        customer_name="World Health Organization",
        business_unit_id=bu.business_unit_id,
    )
    session.add(cust)
    await session.flush()
    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"mxhome-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("50.0000"),
            currency_code="USD",
            revenue_date=date(2026, 3, 1),
            org_id=org.org_id,
            customer_id=cust.customer_id,
            business_unit_id=None,
            division_id=None,
            source_system="excel",
            external_id=f"mxhome-{uid}-1",
            batch_id=None,
        )
    )
    await session.flush()
    token = create_access_token(subject=str(user.user_id))
    return token, str(org.org_id), str(bu.business_unit_id)


@pytest.mark.asyncio
async def test_revenue_matrix_workbook_layout(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENABLE_PHASE7", "true")
    config_module.get_settings.cache_clear()
    try:
        token, org_id = await _seed_user_customer_matrix(db_session)
        r = await async_client.get(
            "/api/v1/revenue/matrix",
            params={"org_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["empty_reason"] is None
        assert len(data["month_columns"]) == 2
        assert len(data["lines"]) == 2
        assert data["lines"][0]["row_type"] == "value"
        assert data["lines"][0]["sr_no"] == 1
        assert data["lines"][0]["customer_legal"] == "Acme Legal"
        assert data["matrix_scope"] == "organization"
        assert data["lines"][0]["customer_id"] is not None
        assert data["lines"][0]["amounts"] == ["100.0000", "130.0000"]
        assert data["lines"][0]["amounts_editable"] is True
        assert data["lines"][1]["row_type"] == "delta"
        assert data["lines"][1]["amounts_editable"] is False
        assert data["lines"][1]["amounts"][0] == ""
        assert data["lines"][1]["amounts"][1] == "30.0000"
    finally:
        config_module.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_revenue_matrix_bu_filter_matches_customer_home_when_fact_bu_null(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENABLE_PHASE7", "true")
    config_module.get_settings.cache_clear()
    try:
        token, org_id, bu_id = await _seed_matrix_customer_home_bu(db_session)
        r = await async_client.get(
            "/api/v1/revenue/matrix",
            params={"org_id": org_id, "business_unit_id": bu_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["empty_reason"] is None
        assert data["matrix_scope"] == "business_unit"
        assert data["lines"][0]["row_type"] == "value"
        assert data["lines"][0]["amounts"] == ["50.0000"]
    finally:
        config_module.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_revenue_matrix_manual_cell_override(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENABLE_PHASE7", "true")
    config_module.get_settings.cache_clear()
    try:
        token, org_id = await _seed_user_customer_matrix(db_session)
        r0 = await async_client.get(
            "/api/v1/revenue/matrix",
            params={"org_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        cust_id = r0.json()["lines"][0]["customer_id"]
        month_key = r0.json()["month_columns"][1]["key"]
        rev_month = datetime.fromisoformat(month_key).date()

        r = await async_client.put(
            "/api/v1/revenue/matrix/cell",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_id": org_id,
                "customer_id": cust_id,
                "revenue_month": rev_month.isoformat(),
                "amount": "200.0000",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["lines"][0]["amounts"] == ["100.0000", "200.0000"]
        assert data["lines"][1]["amounts"][1] == "100.0000"
    finally:
        config_module.get_settings.cache_clear()
