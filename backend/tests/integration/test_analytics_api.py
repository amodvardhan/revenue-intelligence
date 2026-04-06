"""Integration tests for Phase 2 analytics endpoints (requires Postgres)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.dimensions import (
    DimBusinessUnit,
    DimDivision,
    DimOrganization,
    UserBusinessUnitAccess,
    UserOrgRole,
)
from app.models.facts import FactRevenue
from app.models.tenant import Tenant, User


async def _seed_hierarchy_with_facts(session: AsyncSession) -> tuple[str, str]:
    """Return (token, org_id str)."""
    tenant = Tenant(name=f"an-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root Org")
    session.add(org)
    await session.flush()

    bu = DimBusinessUnit(
        tenant_id=tenant.tenant_id,
        org_id=org.org_id,
        business_unit_name="BU1",
    )
    session.add(bu)
    await session.flush()

    div = DimDivision(
        tenant_id=tenant.tenant_id,
        business_unit_id=bu.business_unit_id,
        division_name="Div1",
    )
    session.add(div)
    await session.flush()

    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"an-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))

    for i, amt in enumerate([Decimal("100.0000"), Decimal("50.0000")]):
        session.add(
            FactRevenue(
                tenant_id=tenant.tenant_id,
                amount=amt,
                currency_code="USD",
                revenue_date=date(2026, 1, 15 + i),
                org_id=org.org_id,
                business_unit_id=bu.business_unit_id,
                division_id=div.division_id,
                source_system="test",
                external_id=f"an-{uid}-{i}",
                batch_id=None,
            )
        )
    await session.flush()

    token = create_access_token(subject=str(user.user_id))
    return token, str(org.org_id)


@pytest.mark.asyncio
async def test_rollup_org(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "org",
            "revenue_date_from": "2026-01-01",
            "revenue_date_to": "2026-01-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["hierarchy"] == "org"
    assert len(data["rows"]) == 1
    assert data["rows"][0]["revenue"] == "150.0000"
    assert "as_of" in data


@pytest.mark.asyncio
async def test_rollup_bu(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "bu",
            "revenue_date_from": "2026-01-01",
            "revenue_date_to": "2026-01-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["rows"]) == 1
    assert r.json()["rows"][0]["business_unit_name"] == "BU1"


@pytest.mark.asyncio
async def test_compare_yoy(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/revenue/compare",
        params={
            "hierarchy": "org",
            "compare": "yoy",
            "current_period_from": "2026-01-01",
            "current_period_to": "2026-01-31",
            "comparison_period_from": "2025-01-01",
            "comparison_period_to": "2025-01-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["compare"] == "yoy"
    assert "current_period" in data
    assert data["current_period"]["from"] == "2026-01-01"


@pytest.mark.asyncio
async def test_freshness(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, _ = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/freshness",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "structures" in data
    assert "notes" in data


@pytest.mark.asyncio
async def test_rollup_division(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "division",
            "revenue_date_from": "2026-01-01",
            "revenue_date_to": "2026-01-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["division_name"] == "Div1"


@pytest.mark.asyncio
async def test_compare_bu_hierarchy(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/revenue/compare",
        params={
            "hierarchy": "bu",
            "compare": "mom",
            "current_period_from": "2026-01-01",
            "current_period_to": "2026-01-31",
            "comparison_period_from": "2025-12-01",
            "comparison_period_to": "2025-12-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["rows"][0]["business_unit_name"] == "BU1"


@pytest.mark.asyncio
async def test_bu_restricted_scope_hides_facts(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User with BU access rows only sees those BUs (Phase 2 row-level scoping)."""
    tenant = Tenant(name=f"bu-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="O")
    db_session.add(org)
    await db_session.flush()

    bu_allowed = DimBusinessUnit(
        tenant_id=tenant.tenant_id, org_id=org.org_id, business_unit_name="Allowed"
    )
    bu_other = DimBusinessUnit(
        tenant_id=tenant.tenant_id, org_id=org.org_id, business_unit_name="Other"
    )
    db_session.add_all([bu_allowed, bu_other])
    await db_session.flush()

    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"bu-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))
    db_session.add(
        UserBusinessUnitAccess(user_id=user.user_id, business_unit_id=bu_allowed.business_unit_id)
    )

    db_session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("10.0000"),
            currency_code="USD",
            revenue_date=date(2026, 2, 1),
            org_id=org.org_id,
            business_unit_id=bu_other.business_unit_id,
            source_system="test",
            external_id=f"bu-other-{uid}",
            batch_id=None,
        )
    )
    db_session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("99.0000"),
            currency_code="USD",
            revenue_date=date(2026, 2, 1),
            org_id=org.org_id,
            business_unit_id=bu_allowed.business_unit_id,
            source_system="test",
            external_id=f"bu-ok-{uid}",
            batch_id=None,
        )
    )
    await db_session.flush()

    token = create_access_token(subject=str(user.user_id))
    r = await async_client.get(
        "/api/v1/revenue",
        params={"org_id": str(org.org_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["amount"] == "99.0000"


@pytest.mark.asyncio
async def test_compare_division_hierarchy(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/revenue/compare",
        params={
            "hierarchy": "division",
            "compare": "qoq",
            "current_period_from": "2026-01-01",
            "current_period_to": "2026-01-31",
            "comparison_period_from": "2025-10-01",
            "comparison_period_to": "2025-12-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["division_name"] == "Div1"
    assert row["comparison_missing"] is True


@pytest.mark.asyncio
async def test_rollup_with_revenue_type_filter_no_match(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    fake_rt = "00000000-0000-4000-8000-000000000099"
    r = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "org",
            "revenue_date_from": "2026-01-01",
            "revenue_date_to": "2026-01-31",
            "org_id": org_id,
            "revenue_type_id": fake_rt,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["rows"] == []


@pytest.mark.asyncio
async def test_rollup_validation_bad_range(async_client: AsyncClient, db_session: AsyncSession) -> None:
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "org",
            "revenue_date_from": "2026-02-01",
            "revenue_date_to": "2026-01-01",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


async def _seed_two_business_units_same_org(session: AsyncSession) -> tuple[str, str]:
    """Org with two BUs and one fact each (Story 2.1 child/parent reconciliation)."""
    tenant = Tenant(name=f"2bu-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Multi-BU Org")
    session.add(org)
    await session.flush()

    bu_a = DimBusinessUnit(
        tenant_id=tenant.tenant_id,
        org_id=org.org_id,
        business_unit_name="BU-A",
    )
    bu_b = DimBusinessUnit(
        tenant_id=tenant.tenant_id,
        org_id=org.org_id,
        business_unit_name="BU-B",
    )
    session.add_all([bu_a, bu_b])
    await session.flush()

    div_a = DimDivision(
        tenant_id=tenant.tenant_id,
        business_unit_id=bu_a.business_unit_id,
        division_name="Div-A",
    )
    div_b = DimDivision(
        tenant_id=tenant.tenant_id,
        business_unit_id=bu_b.business_unit_id,
        division_name="Div-B",
    )
    session.add_all([div_a, div_b])
    await session.flush()

    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"2bu-{uid}@example.com",
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
            revenue_date=date(2026, 3, 10),
            org_id=org.org_id,
            business_unit_id=bu_a.business_unit_id,
            division_id=div_a.division_id,
            source_system="test",
            external_id=f"2bu-a-{uid}",
            batch_id=None,
        )
    )
    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("250.0000"),
            currency_code="USD",
            revenue_date=date(2026, 3, 11),
            org_id=org.org_id,
            business_unit_id=bu_b.business_unit_id,
            division_id=div_b.division_id,
            source_system="test",
            external_id=f"2bu-b-{uid}",
            batch_id=None,
        )
    )
    await session.flush()

    token = create_access_token(subject=str(user.user_id))
    return token, str(org.org_id)


@pytest.mark.asyncio
async def test_story_2_1_org_rollup_equals_sum_of_bu_children(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC: Child totals sum to parent — org total matches sum of BU rollups for the same window."""
    token, org_id = await _seed_two_business_units_same_org(db_session)
    params = {
        "revenue_date_from": "2026-03-01",
        "revenue_date_to": "2026-03-31",
        "org_id": org_id,
    }
    r_org = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={"hierarchy": "org", **params},
        headers={"Authorization": f"Bearer {token}"},
    )
    r_bu = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={"hierarchy": "bu", **params},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_org.status_code == 200
    assert r_bu.status_code == 200
    org_rev = Decimal(r_org.json()["rows"][0]["revenue"])
    bu_sum = sum(Decimal(row["revenue"]) for row in r_bu.json()["rows"])
    assert org_rev == bu_sum == Decimal("350.0000")


@pytest.mark.asyncio
async def test_story_2_1_rollup_amounts_match_revenue_list_total(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC: Displayed rollup matches database-derived totals — same as sum of GET /revenue rows."""
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    rollup = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "org",
            "revenue_date_from": "2026-01-01",
            "revenue_date_to": "2026-01-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    lst = await async_client.get(
        "/api/v1/revenue",
        params={
            "org_id": org_id,
            "revenue_date_from": "2026-01-01",
            "revenue_date_to": "2026-01-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rollup.status_code == 200
    assert lst.status_code == 200
    rolled = Decimal(rollup.json()["rows"][0]["revenue"])
    listed = sum(Decimal(i["amount"]) for i in lst.json()["items"])
    assert rolled == listed


@pytest.mark.asyncio
async def test_story_2_1_bu_scope_org_rollup_excludes_other_bus(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC: Row-level BU access — org rollup includes only facts visible under BU restriction."""
    tenant = Tenant(name=f"sc-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Scoped")
    db_session.add(org)
    await db_session.flush()

    bu_allowed = DimBusinessUnit(
        tenant_id=tenant.tenant_id, org_id=org.org_id, business_unit_name="InScope"
    )
    bu_other = DimBusinessUnit(
        tenant_id=tenant.tenant_id, org_id=org.org_id, business_unit_name="OutScope"
    )
    db_session.add_all([bu_allowed, bu_other])
    await db_session.flush()

    div_a = DimDivision(
        tenant_id=tenant.tenant_id,
        business_unit_id=bu_allowed.business_unit_id,
        division_name="D1",
    )
    div_b = DimDivision(
        tenant_id=tenant.tenant_id,
        business_unit_id=bu_other.business_unit_id,
        division_name="D2",
    )
    db_session.add_all([div_a, div_b])
    await db_session.flush()

    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"sc-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))
    db_session.add(
        UserBusinessUnitAccess(user_id=user.user_id, business_unit_id=bu_allowed.business_unit_id)
    )

    for bu, div, amt, ext in (
        (bu_other, div_b, Decimal("10.0000"), f"o-{uid}"),
        (bu_allowed, div_a, Decimal("40.0000"), f"a-{uid}"),
    ):
        db_session.add(
            FactRevenue(
                tenant_id=tenant.tenant_id,
                amount=amt,
                currency_code="USD",
                revenue_date=date(2026, 4, 1),
                org_id=org.org_id,
                business_unit_id=bu.business_unit_id,
                division_id=div.division_id,
                source_system="test",
                external_id=ext,
                batch_id=None,
            )
        )
    await db_session.flush()

    token = create_access_token(subject=str(user.user_id))
    r = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "org",
            "revenue_date_from": "2026-04-01",
            "revenue_date_to": "2026-04-30",
            "org_id": str(org.org_id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["rows"][0]["revenue"] == "40.0000"


@pytest.mark.asyncio
async def test_story_2_2_compare_includes_explicit_period_boundaries(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC: Period boundaries explicit in API (UI uses same contract) — labeled from/to for both legs."""
    token, org_id = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/revenue/compare",
        params={
            "hierarchy": "org",
            "compare": "yoy",
            "current_period_from": "2026-01-01",
            "current_period_to": "2026-01-31",
            "comparison_period_from": "2025-01-01",
            "comparison_period_to": "2025-01-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["current_period"]["from"] == "2026-01-01"
    assert data["current_period"]["to"] == "2026-01-31"
    assert "label" in data["current_period"]
    assert data["comparison_period"]["from"] == "2025-01-01"
    assert data["comparison_period"]["to"] == "2025-01-31"
    assert "label" in data["comparison_period"]
    assert "as_of" in data


@pytest.mark.asyncio
async def test_story_2_2_missing_current_period_not_implied_zero(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC: If data missing for one leg, API does not imply zero revenue — null + flags."""
    tenant = Tenant(name=f"mis-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="O")
    db_session.add(org)
    await db_session.flush()
    bu = DimBusinessUnit(tenant_id=tenant.tenant_id, org_id=org.org_id, business_unit_name="B")
    db_session.add(bu)
    await db_session.flush()
    div = DimDivision(
        tenant_id=tenant.tenant_id, business_unit_id=bu.business_unit_id, division_name="D"
    )
    db_session.add(div)
    await db_session.flush()
    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"mis-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))
    db_session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("77.0000"),
            currency_code="USD",
            revenue_date=date(2025, 1, 15),
            org_id=org.org_id,
            business_unit_id=bu.business_unit_id,
            division_id=div.division_id,
            source_system="test",
            external_id=f"mis-{uid}",
            batch_id=None,
        )
    )
    await db_session.flush()
    token = create_access_token(subject=str(user.user_id))
    r = await async_client.get(
        "/api/v1/analytics/revenue/compare",
        params={
            "hierarchy": "division",
            "compare": "yoy",
            "current_period_from": "2026-01-01",
            "current_period_to": "2026-01-31",
            "comparison_period_from": "2025-01-01",
            "comparison_period_to": "2025-01-31",
            "org_id": str(org.org_id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["current_missing"] is True
    assert row["current_revenue"] is None
    assert row["comparison_missing"] is False
    assert row["comparison_revenue"] == "77.0000"
    assert row["percent_change"] is None


@pytest.mark.asyncio
async def test_story_2_3_drill_down_reconciles_rollup_to_fact_list(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC: Drill-down via GET /revenue uses same facts and reconciles to rolled-up total."""
    token, org_id = await _seed_two_business_units_same_org(db_session)
    rollup = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "org",
            "revenue_date_from": "2026-03-01",
            "revenue_date_to": "2026-03-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    facts = await async_client.get(
        "/api/v1/revenue",
        params={
            "org_id": org_id,
            "revenue_date_from": "2026-03-01",
            "revenue_date_to": "2026-03-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rollup.status_code == 200
    assert facts.status_code == 200
    assert Decimal(rollup.json()["rows"][0]["revenue"]) == sum(
        Decimal(i["amount"]) for i in facts.json()["items"]
    )


@pytest.mark.asyncio
async def test_story_2_3_combined_filters_business_unit_and_dates(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC: Filters combine predictably — BU filter + date window matches single-BU rollup."""
    token, org_id = await _seed_two_business_units_same_org(db_session)
    # Resolve BU-A id from bu rollup
    r_bu = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "bu",
            "revenue_date_from": "2026-03-01",
            "revenue_date_to": "2026-03-31",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    bu_a_id = next(
        row["business_unit_id"]
        for row in r_bu.json()["rows"]
        if row["business_unit_name"] == "BU-A"
    )
    r_filtered = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "org",
            "revenue_date_from": "2026-03-01",
            "revenue_date_to": "2026-03-31",
            "org_id": org_id,
            "business_unit_id": bu_a_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_filtered.status_code == 200
    assert r_filtered.json()["rows"][0]["revenue"] == "100.0000"


@pytest.mark.asyncio
async def test_story_2_4_freshness_contract_documents_refresh_and_tenant(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC: Freshness / operational clarity — response identifies tenant and carries guidance notes."""
    token, _ = await _seed_hierarchy_with_facts(db_session)
    r = await async_client.get(
        "/api/v1/analytics/freshness",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert UUID(data["tenant_id"])
    assert isinstance(data["structures"], list)
    assert "notes" in data and len(data["notes"]) > 0


@pytest.mark.asyncio
async def test_analytics_endpoints_require_auth(async_client: AsyncClient) -> None:
    """Regression: analytics routes stay behind authentication (valid params, no token → 401)."""
    common_dates = {
        "revenue_date_from": "2026-01-01",
        "revenue_date_to": "2026-01-31",
    }
    r1 = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={"hierarchy": "org", **common_dates},
    )
    assert r1.status_code == 401
    r2 = await async_client.get(
        "/api/v1/analytics/revenue/compare",
        params={
            "hierarchy": "org",
            "compare": "yoy",
            "current_period_from": "2026-01-01",
            "current_period_to": "2026-01-31",
            "comparison_period_from": "2025-01-01",
            "comparison_period_to": "2025-01-31",
        },
    )
    assert r2.status_code == 401
    r3 = await async_client.get("/api/v1/analytics/freshness")
    assert r3.status_code == 401
