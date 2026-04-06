"""Phase 4 HubSpot — acceptance tests for Stories 4.1–4.3 (requires Postgres)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.models.dimensions import DimCustomer, DimOrganization, UserOrgRole
from app.models.facts import FactRevenue
from app.models.hubspot_integration import (
    HubspotConnection,
    HubspotIdMapping,
    HubspotSyncCursor,
    IntegrationSyncRun,
    RevenueSourceConflict,
)
from app.models.tenant import Tenant, User
from app.services.integrations.hubspot.crypto_bundle import encrypt_token_bundle
from app.services.integrations.hubspot.reconciliation import detect_revenue_conflicts
from app.services.integrations.hubspot.sync_service import OBJECT_DEALS, run_hubspot_sync


@pytest.fixture
def hubspot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_HUBSPOT", "true")
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("HUBSPOT_REDIRECT_URI", "http://test.local/oauth/callback")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _seed_user_with_role(
    session: AsyncSession,
    *,
    role: str,
) -> tuple[str, "Tenant", "User", "DimOrganization"]:
    tenant = Tenant(name=f"hs-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="Root")
    session.add(org)
    await session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"hs-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("x"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role=role))
    await session.flush()
    token = create_access_token(subject=str(user.user_id))
    return token, tenant, user, org


@pytest.mark.asyncio
async def test_story_4_1_hubspot_disabled_returns_503(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When integration is off, operators get explicit service-unavailable (not a silent empty UI)."""
    monkeypatch.setenv("ENABLE_HUBSPOT", "false")
    get_settings.cache_clear()
    try:
        token, _, _, _ = await _seed_user_with_role(db_session, role="it_admin")
        r = await async_client.get(
            "/api/v1/integrations/hubspot/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 503
        assert r.json()["detail"]["error"]["code"] == "SERVICE_UNAVAILABLE"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_story_4_1_status_surfaces_connected_error_and_token_refresh_failed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    hubspot_env: None,
) -> None:
    """Connection status includes connected, error strings, and token_refresh_failed visibility."""
    token, tenant, _, _ = await _seed_user_with_role(db_session, role="finance")
    conn = HubspotConnection(
        tenant_id=tenant.tenant_id,
        status="token_refresh_failed",
        hubspot_portal_id="12345",
        encrypted_token_bundle=None,
        token_expires_at=None,
        last_error="OAuth refresh failed — reconnect HubSpot.",
    )
    db_session.add(conn)
    await db_session.flush()

    r = await async_client.get(
        "/api/v1/integrations/hubspot/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "token_refresh_failed"
    assert body["last_error"] is not None
    assert "refresh" in body["last_error"].lower()


@pytest.mark.asyncio
async def test_story_4_1_authorize_url_requires_it_admin(
    async_client: AsyncClient,
    db_session: AsyncSession,
    hubspot_env: None,
) -> None:
    """Finance cannot start OAuth; IT Admin (or admin) can (least privilege on connect)."""
    fin_token, _, _, _ = await _seed_user_with_role(db_session, role="finance")
    r_fin = await async_client.get(
        "/api/v1/integrations/hubspot/oauth/authorize-url",
        headers={"Authorization": f"Bearer {fin_token}"},
    )
    assert r_fin.status_code == 403

    admin_token, _, _, _ = await _seed_user_with_role(db_session, role="it_admin")
    r_ok = await async_client.get(
        "/api/v1/integrations/hubspot/oauth/authorize-url",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_ok.status_code == 200
    data = r_ok.json()
    assert "authorization_url" in data
    assert "test-client-id" in data["authorization_url"]
    assert "state" in data


@pytest.mark.asyncio
async def test_story_4_2_sync_returns_202_and_enqueues_task(
    async_client: AsyncClient,
    db_session: AsyncSession,
    hubspot_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Long-running sync is async (202) with feedback; worker entrypoint is invoked (Celery)."""
    token, tenant, user, _ = await _seed_user_with_role(db_session, role="it_admin")
    bundle = encrypt_token_bundle({"access_token": "a", "refresh_token": "r"})
    db_session.add(
        HubspotConnection(
            tenant_id=tenant.tenant_id,
            status="connected",
            hubspot_portal_id="p1",
            encrypted_token_bundle=bundle,
            token_expires_at=datetime.now(tz=UTC) + timedelta(days=1),
        )
    )
    await db_session.flush()

    mock_task = MagicMock()
    monkeypatch.setattr("app.tasks.sync_tasks.run_hubspot_sync_task", mock_task)

    r = await async_client.post(
        "/api/v1/integrations/hubspot/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"mode": "incremental"},
    )
    assert r.status_code == 202
    assert "sync_run_id" in r.json()
    assert mock_task.delay.called

    list_r = await async_client.get(
        "/api/v1/integrations/hubspot/sync-runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_r.status_code == 200
    items = list_r.json()["items"]
    assert len(items) >= 1
    row = items[0]
    assert row["status"] in ("running", "completed", "failed")
    assert row["trigger"] == "manual"
    assert "started_at" in row
    assert "correlation_id" in row


@pytest.mark.asyncio
async def test_story_4_2_incremental_sync_uses_search_after_cursor_not_full_list(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental path uses hs_lastmodifieddate cursor (search) — not full table reload — when cursor exists."""
    tenant = Tenant(name=f"sync-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"sync-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("x"),
    )
    db_session.add(user)
    await db_session.flush()

    bundle = encrypt_token_bundle({"access_token": "a", "refresh_token": "r"})
    db_session.add(
        HubspotConnection(
            tenant_id=tenant.tenant_id,
            status="connected",
            hubspot_portal_id="x",
            encrypted_token_bundle=bundle,
            token_expires_at=datetime.now(tz=UTC) + timedelta(days=1),
        )
    )
    db_session.add(
        HubspotSyncCursor(
            tenant_id=tenant.tenant_id,
            object_type=OBJECT_DEALS,
            cursor_payload={"last_modified_ms": 5000},
        )
    )
    run = IntegrationSyncRun(
        tenant_id=tenant.tenant_id,
        integration_code="hubspot",
        trigger="manual",
        initiated_by_user_id=user.user_id,
        status="running",
    )
    db_session.add(run)
    await db_session.flush()
    sync_run_id = run.sync_run_id

    search_calls: list[dict] = []

    class FakeApi:
        def __init__(self, _token: str) -> None:
            pass

        async def search_deals_modified_after(self, **kwargs: object) -> dict:
            search_calls.append(dict(kwargs))
            return {"results": [], "paging": {}}

        async def list_deals_page(self, **_kwargs: object) -> dict:
            raise AssertionError("full list should not run when incremental cursor is present")

    from app.services.integrations.hubspot import sync_service as sync_mod

    monkeypatch.setattr(sync_mod, "HubspotApiClient", FakeApi)

    await run_hubspot_sync(db_session, tenant_id=tenant.tenant_id, sync_run_id=sync_run_id, mode="incremental")
    assert len(search_calls) >= 1
    assert search_calls[0]["after_ms"] == 5000


@pytest.mark.asyncio
async def test_story_4_2_repair_mode_does_not_use_incremental_search(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repair mode re-fetches deals (full list path) even when a cursor exists."""
    tenant = Tenant(name=f"rep-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"rep-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("x"),
    )
    db_session.add(user)
    await db_session.flush()

    bundle = encrypt_token_bundle({"access_token": "a", "refresh_token": "r"})
    db_session.add(
        HubspotConnection(
            tenant_id=tenant.tenant_id,
            status="connected",
            encrypted_token_bundle=bundle,
            token_expires_at=datetime.now(tz=UTC) + timedelta(days=1),
        )
    )
    db_session.add(
        HubspotSyncCursor(
            tenant_id=tenant.tenant_id,
            object_type=OBJECT_DEALS,
            cursor_payload={"last_modified_ms": 99999},
        )
    )
    run = IntegrationSyncRun(
        tenant_id=tenant.tenant_id,
        integration_code="hubspot",
        trigger="manual",
        initiated_by_user_id=user.user_id,
        status="running",
    )
    db_session.add(run)
    await db_session.flush()

    list_calls = 0

    class FakeApi:
        def __init__(self, _token: str) -> None:
            pass

        async def search_deals_modified_after(self, **_kwargs: object) -> dict:
            raise AssertionError("search should not run in repair mode")

        async def list_deals_page(self, **_kwargs: object) -> dict:
            nonlocal list_calls
            list_calls += 1
            return {"results": [], "paging": {}}

    from app.services.integrations.hubspot import sync_service as sync_mod

    monkeypatch.setattr(sync_mod, "HubspotApiClient", FakeApi)

    await run_hubspot_sync(db_session, tenant_id=tenant.tenant_id, sync_run_id=run.sync_run_id, mode="repair")
    assert list_calls >= 1


@pytest.mark.asyncio
async def test_story_4_2_partial_failure_surfaces_completed_with_errors_and_counts(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When some deals fail mapping and some succeed, run is not silent success (PRD data accuracy)."""
    tenant = Tenant(name=f"pf-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"pf-{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("x"),
    )
    db_session.add(user)
    await db_session.flush()

    bundle = encrypt_token_bundle({"access_token": "a", "refresh_token": "r"})
    db_session.add(
        HubspotConnection(
            tenant_id=tenant.tenant_id,
            status="connected",
            encrypted_token_bundle=bundle,
            token_expires_at=datetime.now(tz=UTC) + timedelta(days=1),
        )
    )
    run = IntegrationSyncRun(
        tenant_id=tenant.tenant_id,
        integration_code="hubspot",
        trigger="manual",
        initiated_by_user_id=user.user_id,
        status="running",
    )
    db_session.add(run)
    await db_session.flush()

    sample_deal = {
        "id": "111",
        "properties": {
            "dealname": "D",
            "amount": "100",
            "closedate": "2026-01-15",
            "pipeline": "p",
            "dealstage": "s",
            "hs_lastmodifieddate": "10000",
            "hs_object_id": "111",
        },
        "associations": {"companies": {"results": [{"id": "999"}]}},
    }

    class FakeApi:
        def __init__(self, _token: str) -> None:
            pass

        async def list_deals_page(self, **_kwargs: object) -> dict:
            return {"results": [sample_deal, sample_deal], "paging": {}}

    from app.services.integrations.hubspot import sync_service as sync_mod

    monkeypatch.setattr(sync_mod, "HubspotApiClient", FakeApi)
    # First deal loads; second fails mapping — surfaces completed_with_errors, not silent OK.
    monkeypatch.setattr(
        sync_mod,
        "_process_deal",
        AsyncMock(side_effect=[True, False]),
    )

    await run_hubspot_sync(db_session, tenant_id=tenant.tenant_id, sync_run_id=run.sync_run_id, mode="repair")
    await db_session.refresh(run)
    assert run.rows_fetched == 2
    assert run.rows_loaded == 1
    assert run.rows_failed == 1
    assert run.status == "completed_with_errors"
    assert run.error_summary


@pytest.mark.asyncio
async def test_story_4_3_mapping_exceptions_list_pending_unmapped(
    async_client: AsyncClient,
    db_session: AsyncSession,
    hubspot_env: None,
) -> None:
    """Unmapped HubSpot objects surface as exceptions, not silent misclassification."""
    token, tenant, _, _ = await _seed_user_with_role(db_session, role="finance")
    db_session.add(
        HubspotIdMapping(
            tenant_id=tenant.tenant_id,
            hubspot_object_type="company",
            hubspot_object_id="hs-comp-1",
            status="pending",
        )
    )
    await db_session.flush()

    r = await async_client.get(
        "/api/v1/integrations/hubspot/mapping-exceptions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["hubspot_object_id"] == "hs-comp-1" and i["status"] == "pending" for i in items)


@pytest.mark.asyncio
async def test_story_4_3_reconciliation_report_compares_excel_and_hubspot_totals(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Finance can compare HubSpot-sourced aggregates to Excel-sourced aggregates (same period)."""
    token, tenant, _, org = await _seed_user_with_role(db_session, role="finance")
    cust = DimCustomer(
        tenant_id=tenant.tenant_id,
        customer_name="C1",
        org_id=org.org_id,
    )
    db_session.add(cust)
    await db_session.flush()
    rid = date(2026, 3, 10)
    db_session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("1000.0000"),
            currency_code="USD",
            revenue_date=rid,
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="excel",
            external_id="ex-1",
            batch_id=None,
        )
    )
    db_session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("900.0000"),
            currency_code="USD",
            revenue_date=rid,
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="hubspot",
            external_id="hs-deal-1",
            batch_id=None,
        )
    )
    await db_session.flush()

    r = await async_client.get(
        "/api/v1/analytics/revenue/source-reconciliation",
        params={
            "revenue_date_from": "2026-03-01",
            "revenue_date_to": "2026-03-31",
            "grain": "customer",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["revenue_date_from"] == "2026-03-01"
    rows = payload["rows"]
    assert len(rows) >= 1
    match = next(
        (x for x in rows if x.get("customer_id") == str(cust.customer_id)),
        None,
    )
    assert match is not None
    assert match["excel_total"] == "1000.0000"
    assert match["hubspot_total"] == "900.0000"
    assert match["variance"] != "0"


@pytest.mark.asyncio
async def test_story_4_3_detect_revenue_conflicts_surfaces_excel_vs_hubspot_mismatch(
    db_session: AsyncSession,
) -> None:
    """Conflicts between Excel and HubSpot for the same canonical key appear in revenue_source_conflict."""
    tenant = Tenant(name=f"cf-{uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="O2")
    db_session.add(org)
    await db_session.flush()
    cust = DimCustomer(
        tenant_id=tenant.tenant_id,
        customer_name="C2",
        org_id=org.org_id,
    )
    db_session.add(cust)
    await db_session.flush()
    rd = date(2026, 4, 1)
    db_session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("500.0000"),
            currency_code="USD",
            revenue_date=rd,
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="excel",
            external_id="e-cf-1",
            batch_id=None,
        )
    )
    db_session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("700.0000"),
            currency_code="USD",
            revenue_date=rd,
            org_id=org.org_id,
            customer_id=cust.customer_id,
            source_system="hubspot",
            external_id="hs-cf-1",
            batch_id=None,
        )
    )
    await db_session.flush()

    n = await detect_revenue_conflicts(db_session, tenant_id=tenant.tenant_id)
    assert n >= 1
    res = await db_session.execute(
        select(RevenueSourceConflict).where(RevenueSourceConflict.tenant_id == tenant.tenant_id)
    )
    conflicts = res.scalars().all()
    assert any(c.status == "open" for c in conflicts)


@pytest.mark.asyncio
async def test_story_4_3_revenue_conflicts_api_lists_rows(
    async_client: AsyncClient,
    db_session: AsyncSession,
    hubspot_env: None,
) -> None:
    token, tenant, _, _ = await _seed_user_with_role(db_session, role="finance")
    db_session.add(
        RevenueSourceConflict(
            tenant_id=tenant.tenant_id,
            reconciliation_key=f"{tenant.tenant_id}:k",
            excel_amount=Decimal("1.0000"),
            hubspot_amount=Decimal("2.0000"),
            status="open",
        )
    )
    await db_session.flush()

    r = await async_client.get(
        "/api/v1/integrations/hubspot/revenue-conflicts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1
