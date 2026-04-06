"""Phase 5 — acceptance criteria (Stories 5.1–5.4) via API + DB seeding."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config as config_module
from app.core.security import create_access_token, hash_password
from app.models.dimensions import (
    DimBusinessUnit,
    DimCustomer,
    DimDivision,
    DimOrganization,
    UserOrgRole,
)
from app.models.facts import FactRevenue
from app.models.phase5 import FactCost, FactForecast, ForecastSeries, FxRate
from app.models.tenant import Tenant, User


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, monthrange(y, m)[1])
    return date(y, m, day)


def _enable_phase5(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_PHASE5", "true")
    config_module.get_settings.cache_clear()


async def _seed_hierarchy_finance(
    session: AsyncSession,
) -> tuple[str, UUID, UUID, UUID, UUID, UUID]:
    """Returns token, tenant_id, org_id, bu_id, div_id, user_id."""
    tenant = Tenant(name=f"p5i-{uuid4().hex[:10]}")
    session.add(tenant)
    await session.flush()

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="P5 Org")
    session.add(org)
    await session.flush()

    bu = DimBusinessUnit(
        tenant_id=tenant.tenant_id,
        org_id=org.org_id,
        business_unit_name="P5 BU",
    )
    session.add(bu)
    await session.flush()

    div = DimDivision(
        tenant_id=tenant.tenant_id,
        business_unit_id=bu.business_unit_id,
        division_name="P5 Div",
    )
    session.add(div)
    await session.flush()

    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"p5i-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))
    await session.flush()

    token = create_access_token(subject=str(user.user_id))
    return token, tenant.tenant_id, org.org_id, bu.business_unit_id, div.division_id, user.user_id


@pytest.mark.asyncio
async def test_story_5_4_tenant_single_reporting_currency(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.4 — single reporting currency per tenant (default USD path via API)."""
    _enable_phase5(monkeypatch)
    token, *_rest = await _seed_hierarchy_finance(db_session)
    r = await async_client.get(
        "/api/v1/tenant/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reporting_currency_code"] == "USD"


@pytest.mark.asyncio
async def test_story_5_4_consolidated_native_and_fx_metadata(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.4 — consolidated rollup shows reporting currency, native breakdown, FX basis note."""
    _enable_phase5(monkeypatch)
    token, tenant_id, org_id, bu_id, div_id, _uid = await _seed_hierarchy_finance(db_session)

    session = db_session
    session.add(
        FxRate(
            tenant_id=tenant_id,
            base_currency_code="EUR",
            quote_currency_code="USD",
            effective_date=date(2025, 1, 2),
            rate=Decimal("1.1000000000"),
            rate_source="manual_upload",
        )
    )
    session.add(
        FactRevenue(
            tenant_id=tenant_id,
            amount=Decimal("100.0000"),
            currency_code="EUR",
            revenue_date=date(2026, 1, 15),
            org_id=org_id,
            business_unit_id=bu_id,
            division_id=div_id,
            source_system="p5test",
            external_id=f"eur-{uuid4().hex[:8]}",
            batch_id=None,
        )
    )
    await session.flush()

    r = await async_client.get(
        "/api/v1/analytics/revenue/consolidated",
        params={
            "hierarchy": "org",
            "revenue_date_from": "2026-01-01",
            "revenue_date_to": "2026-01-31",
            "include_native_amounts": "true",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["metric"] == "actuals"
    assert data["rows"][0]["reporting_currency_code"] == "USD"
    assert "fx_basis_note" in data["rows"][0]
    nb = data["rows"][0]["native_breakdown"][0]
    assert nb["native_currency_code"] == "EUR"
    assert nb["fx_pair"] == "EUR/USD"
    assert "fx_rate_effective_date" in nb
    assert float(nb["reporting_amount"]) == pytest.approx(110.0)


@pytest.mark.asyncio
async def test_story_5_4_missing_fx_returns_fx_rate_missing(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.4 — no silent FX: missing pair surfaces FX_RATE_MISSING."""
    _enable_phase5(monkeypatch)
    token, tenant_id, org_id, bu_id, div_id, _uid = await _seed_hierarchy_finance(db_session)

    db_session.add(
        FactRevenue(
            tenant_id=tenant_id,
            amount=Decimal("50.0000"),
            currency_code="JPY",
            revenue_date=date(2026, 2, 10),
            org_id=org_id,
            business_unit_id=bu_id,
            division_id=div_id,
            source_system="p5test",
            external_id=f"jpy-{uuid4().hex[:8]}",
            batch_id=None,
        )
    )
    await db_session.flush()

    r = await async_client.get(
        "/api/v1/analytics/revenue/consolidated",
        params={
            "hierarchy": "org",
            "revenue_date_from": "2026-02-01",
            "revenue_date_to": "2026-02-28",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "FX_RATE_MISSING"


@pytest.mark.asyncio
async def test_story_5_4_fx_list_shows_rate_source_and_effective_date(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.4 — FX table exposes effective date and rate source label."""
    _enable_phase5(monkeypatch)
    token, tenant_id, *_ = await _seed_hierarchy_finance(db_session)

    db_session.add(
        FxRate(
            tenant_id=tenant_id,
            base_currency_code="GBP",
            quote_currency_code="USD",
            effective_date=date(2026, 3, 1),
            rate=Decimal("1.2500000000"),
            rate_source="manual_upload",
        )
    )
    await db_session.flush()

    r = await async_client.get(
        "/api/v1/fx-rates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(
        i["base_currency_code"] == "GBP"
        and i["quote_currency_code"] == "USD"
        and i["effective_date"] == "2026-03-01"
        and i["rate_source"] == "manual_upload"
        for i in items
    )


@pytest.mark.asyncio
async def test_story_5_2_profitability_margin_and_cost_scope_note(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.2 — margin uses NUMERIC legs; methodology states cost scope (COGS vs full)."""
    _enable_phase5(monkeypatch)
    token, tenant_id, org_id, bu_id, div_id, _uid = await _seed_hierarchy_finance(db_session)

    db_session.add(
        FactRevenue(
            tenant_id=tenant_id,
            amount=Decimal("200.0000"),
            currency_code="USD",
            revenue_date=date(2026, 4, 1),
            org_id=org_id,
            business_unit_id=bu_id,
            division_id=div_id,
            source_system="p5test",
            external_id=f"rev-{uuid4().hex[:8]}",
            batch_id=None,
        )
    )
    db_session.add(
        FactCost(
            tenant_id=tenant_id,
            amount=Decimal("50.0000"),
            currency_code="USD",
            cost_date=date(2026, 4, 5),
            cost_category="cogs",
            org_id=org_id,
            business_unit_id=bu_id,
            source_system="cost_csv",
            external_id=f"cost-{uuid4().hex[:8]}",
            batch_id=None,
        )
    )
    await db_session.flush()

    r = await async_client.get(
        "/api/v1/analytics/profitability/summary",
        params={
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "cost_scope": "cogs_only",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["revenue_total"] == "200.0000"
    assert body["cost_total"] == "50.0000"
    assert body["margin"] == "150.0000"
    assert body["cost_scope"] == "cogs_only"
    assert "cogs" in body["methodology_note"].lower()


@pytest.mark.asyncio
async def test_story_5_2_cost_facts_traceable(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.2 — reconciliation path: cost facts list exposes source and amounts."""
    _enable_phase5(monkeypatch)
    token, tenant_id, org_id, _bu, _div, _uid = await _seed_hierarchy_finance(db_session)

    db_session.add(
        FactCost(
            tenant_id=tenant_id,
            amount=Decimal("12.3400"),
            currency_code="USD",
            cost_date=date(2026, 5, 1),
            cost_category="cogs",
            org_id=org_id,
            source_system="cost_csv",
            external_id=f"cx-{uuid4().hex[:10]}",
            batch_id=None,
        )
    )
    await db_session.flush()

    r = await async_client.get(
        "/api/v1/costs/facts",
        params={"cost_date_from": "2026-05-01", "cost_date_to": "2026-05-31"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["amount"] == "12.3400" and i["source_system"] == "cost_csv" for i in items)


@pytest.mark.asyncio
async def test_story_5_2_allocation_rule_versioning(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.2 — allocation rules carry version label and effective dates (no silent rewrite)."""
    _enable_phase5(monkeypatch)
    token, tenant_id, org_id, _bu, _div, _uid = await _seed_hierarchy_finance(db_session)

    r = await async_client.post(
        "/api/v1/costs/allocation-rules",
        json={
            "version_label": "FY26-v1",
            "effective_from": "2026-01-01",
            "basis": "revenue_share",
            "rule_definition": {"pool": "shared_services", "org_id": str(org_id)},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201

    lr = await async_client.get(
        "/api/v1/costs/allocation-rules",
        params={"effective_on": "2026-06-15"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lr.status_code == 200
    items = lr.json()["items"]
    assert any(i["version_label"] == "FY26-v1" and i["basis"] == "revenue_share" for i in items)


@pytest.mark.asyncio
async def test_story_5_1_forecast_vs_actual_explicit_separation(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.1 — actuals vs forecast not merged; labels and period boundary note."""
    _enable_phase5(monkeypatch)
    token, tenant_id, org_id, bu_id, div_id, _uid = await _seed_hierarchy_finance(db_session)

    fs = ForecastSeries(
        tenant_id=tenant_id,
        label="Board plan",
        scenario="base",
        source_mode="imported",
        methodology={"upload": "seed"},
    )
    db_session.add(fs)
    await db_session.flush()

    db_session.add(
        FactRevenue(
            tenant_id=tenant_id,
            amount=Decimal("1000.0000"),
            currency_code="USD",
            revenue_date=date(2026, 6, 10),
            org_id=org_id,
            business_unit_id=bu_id,
            division_id=div_id,
            source_system="p5test",
            external_id=f"act-{uuid4().hex[:8]}",
            batch_id=None,
        )
    )
    db_session.add(
        FactForecast(
            tenant_id=tenant_id,
            forecast_series_id=fs.forecast_series_id,
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            amount=Decimal("500.0000"),
            currency_code="USD",
            org_id=org_id,
            external_id="fc-1",
            batch_id=None,
        )
    )
    await db_session.flush()

    r = await async_client.get(
        "/api/v1/analytics/revenue/forecast-vs-actual",
        params={
            "forecast_series_id": str(fs.forecast_series_id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "hierarchy": "org",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["series_actual"]["metric"] == "booked_actuals"
    assert body["series_forecast"]["metric"] == "forecast"
    assert body["series_actual"]["total"] == "1000.0000"
    assert body["series_forecast"]["total"] == "500.0000"
    assert body["source_mode"] == "imported"
    assert "period_boundary_note" in body


@pytest.mark.asyncio
async def test_story_5_1_forecast_series_filters_source_mode(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.1 — hybrid labeling: list filter by imported vs statistical."""
    _enable_phase5(monkeypatch)
    token, tenant_id, *_ = await _seed_hierarchy_finance(db_session)

    db_session.add(
        ForecastSeries(
            tenant_id=tenant_id,
            label="Imported A",
            source_mode="imported",
            methodology={},
        )
    )
    db_session.add(
        ForecastSeries(
            tenant_id=tenant_id,
            label="Stat B",
            source_mode="statistical",
            methodology={"model_family": "trailing_monthly_average"},
        )
    )
    await db_session.flush()

    ri = await async_client.get(
        "/api/v1/forecast/series",
        params={"source_mode": "imported"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ri.status_code == 200
    assert all(x["source_mode"] == "imported" for x in ri.json()["items"])

    rs = await async_client.get(
        "/api/v1/forecast/series",
        params={"source_mode": "statistical"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rs.status_code == 200
    assert all(x["source_mode"] == "statistical" for x in rs.json()["items"])


@pytest.mark.asyncio
async def test_story_5_1_two_imports_create_distinct_series_ids(
    async_client_ingest: AsyncClient, db_session_with_flush_commit: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.1 — versioning: new upload creates a new series (no silent overwrite)."""
    _enable_phase5(monkeypatch)
    token, _tid, org_id, _bu, _div, _uid = await _seed_hierarchy_finance(db_session_with_flush_commit)

    csv_a = b"period_start,period_end,amount,currency_code\n2026-07-01,2026-07-31,10,USD\n"
    csv_b = b"period_start,period_end,amount,currency_code\n2026-08-01,2026-08-31,20,USD\n"

    r1 = await async_client_ingest.post(
        "/api/v1/ingest/forecast-uploads",
        headers={"Authorization": f"Bearer {token}"},
        data={"org_id": str(org_id), "label": "First"},
        files={"file": ("a.csv", BytesIO(csv_a), "text/csv")},
    )
    r2 = await async_client_ingest.post(
        "/api/v1/ingest/forecast-uploads",
        headers={"Authorization": f"Bearer {token}"},
        data={"org_id": str(org_id), "label": "Second"},
        files={"file": ("b.csv", BytesIO(csv_b), "text/csv")},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    id1 = r1.json()["forecast_series_id"]
    id2 = r2.json()["forecast_series_id"]
    assert id1 != id2


@pytest.mark.asyncio
async def test_story_5_1_statistical_refresh_requires_history(
    async_client_ingest: AsyncClient, db_session_with_flush_commit: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.1 — statistical baseline documents methodology when history exists."""
    _enable_phase5(monkeypatch)
    token, tenant_id, org_id, bu_id, div_id, _uid = await _seed_hierarchy_finance(
        db_session_with_flush_commit
    )
    session = db_session_with_flush_commit

    end_hist = date.today().replace(day=1) - timedelta(days=1)
    start_hist = _add_months(_month_start(end_hist), -11)
    hist_date = min(end_hist, start_hist + timedelta(days=5))

    session.add(
        FactRevenue(
            tenant_id=tenant_id,
            amount=Decimal("300.0000"),
            currency_code="USD",
            revenue_date=hist_date,
            org_id=org_id,
            business_unit_id=bu_id,
            division_id=div_id,
            source_system="p5test",
            external_id=f"hist-{uuid4().hex[:8]}",
            batch_id=None,
        )
    )
    fs = ForecastSeries(
        tenant_id=tenant_id,
        label="Stat seed",
        source_mode="imported",
        methodology={},
    )
    session.add(fs)
    await session.flush()

    r = await async_client_ingest.post(
        f"/api/v1/forecast/series/{fs.forecast_series_id}/statistical-refresh",
        headers={"Authorization": f"Bearer {token}"},
        json={"horizon_months": 2, "method": "trailing_average"},
    )
    assert r.status_code == 202
    assert r.json()["source_mode"] == "statistical"

    detail = await async_client_ingest.get(
        f"/api/v1/forecast/series/{fs.forecast_series_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    meth = detail.json().get("methodology") or {}
    assert meth.get("model_family") == "trailing_monthly_average"


@pytest.mark.asyncio
async def test_story_5_3_segment_materialize_replayable(
    async_client_ingest: AsyncClient, db_session_with_flush_commit: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.3 — stored rule + materialize yields stable membership for org scope."""
    _enable_phase5(monkeypatch)
    token, tenant_id, org_id, _bu, _div, _uid = await _seed_hierarchy_finance(
        db_session_with_flush_commit
    )
    session = db_session_with_flush_commit

    cust = DimCustomer(
        tenant_id=tenant_id,
        customer_name="Seg Customer",
        org_id=org_id,
    )
    session.add(cust)
    await session.flush()

    cr = await async_client_ingest.post(
        "/api/v1/segments/definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Enterprise-{uuid4().hex[:6]}",
            "owner_org_id": str(org_id),
            "rule_definition": {"type": "customers_in_org", "org_id": str(org_id)},
        },
    )
    assert cr.status_code == 201
    seg_id = cr.json()["segment_id"]

    mat = await async_client_ingest.post(
        f"/api/v1/segments/definitions/{seg_id}/materialize",
        headers={"Authorization": f"Bearer {token}"},
        json={"period_start": "2026-01-01", "period_end": "2026-12-31"},
    )
    assert mat.status_code == 202
    assert mat.json()["membership_rows"] >= 1

    m2 = await async_client_ingest.post(
        f"/api/v1/segments/definitions/{seg_id}/materialize",
        headers={"Authorization": f"Bearer {token}"},
        json={"period_start": "2026-01-01", "period_end": "2026-12-31"},
    )
    assert m2.status_code == 202

    lr = await async_client_ingest.get(
        f"/api/v1/segments/definitions/{seg_id}/membership",
        params={"period_start": "2026-01-01", "period_end": "2026-12-31"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lr.status_code == 200
    assert any(x["customer_id"] == str(cust.customer_id) for x in lr.json()["items"])
