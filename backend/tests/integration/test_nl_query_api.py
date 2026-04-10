"""Phase 3 NL query API (requires Postgres + Phase 3 migration)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.dimensions import (
    DimBusinessUnit,
    DimCustomer,
    DimDivision,
    DimOrganization,
    UserOrgRole,
)
from app.models.facts import FactRevenue
from app.models.phase7 import RevenueVarianceComment
from app.models.tenant import Tenant, User


@pytest_asyncio.fixture
async def phase3_tables(db_session: AsyncSession) -> None:
    res = await db_session.execute(text("SELECT to_regclass('public.semantic_layer_version')"))
    if res.scalar() is None:
        pytest.fail(
            "public.semantic_layer_version is missing. Integration sessions auto-run "
            "`alembic upgrade head` (see tests/conftest.py). Set PYTEST_SKIP_ALEMBIC_UPGRADE=1 "
            "only if you run migrations manually; otherwise fix DATABASE_URL and Postgres."
        )


async def _seed_nl_user(session: AsyncSession) -> tuple[str, str]:
    tenant = Tenant(name=f"nl-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="NL Org")
    session.add(org)
    await session.flush()

    bu = DimBusinessUnit(
        tenant_id=tenant.tenant_id,
        org_id=org.org_id,
        business_unit_name="NL BU",
    )
    session.add(bu)
    await session.flush()

    div = DimDivision(
        tenant_id=tenant.tenant_id,
        business_unit_id=bu.business_unit_id,
        division_name="NL Div",
    )
    session.add(div)
    await session.flush()

    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"nl-{uid}@example.com",
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
            revenue_date=date(2026, 7, 15),
            org_id=org.org_id,
            business_unit_id=bu.business_unit_id,
            division_id=div.division_id,
            source_system="test",
            external_id=f"nl-{uid}-1",
            batch_id=None,
        )
    )
    await session.flush()

    token = create_access_token(subject=str(user.user_id))
    return token, str(org.org_id)


async def _seed_nl_user_with_who_customer(session: AsyncSession) -> tuple[str, str]:
    """Tenant with dim_customer WHO + March 2026 fact (customer-scoped NL)."""
    tenant = Tenant(name=f"nlwho-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="e-Zest Digital Solutions")
    session.add(org)
    await session.flush()

    bu = DimBusinessUnit(
        tenant_id=tenant.tenant_id,
        org_id=org.org_id,
        business_unit_name="NL BU",
    )
    session.add(bu)
    await session.flush()

    div = DimDivision(
        tenant_id=tenant.tenant_id,
        business_unit_id=bu.business_unit_id,
        division_name="NL Div",
    )
    session.add(div)
    await session.flush()

    cust = DimCustomer(
        tenant_id=tenant.tenant_id,
        customer_name="World Health Organization",
        org_id=org.org_id,
    )
    session.add(cust)
    await session.flush()

    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"nlwho-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))

    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("1292150.9400"),
            currency_code="USD",
            revenue_date=date(2026, 3, 10),
            org_id=org.org_id,
            business_unit_id=bu.business_unit_id,
            division_id=div.division_id,
            customer_id=cust.customer_id,
            source_system="test",
            external_id=f"nlwho-{uid}-1",
            batch_id=None,
        )
    )
    await session.flush()

    token = create_access_token(subject=str(user.user_id))
    return token, str(org.org_id)


async def _seed_viewer_nl_user(session: AsyncSession) -> tuple[str, str]:
    """Viewer may use NL but cannot access query audit APIs."""
    tenant = Tenant(name=f"nlv-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="NL Viewer Org")
    session.add(org)
    await session.flush()

    bu = DimBusinessUnit(
        tenant_id=tenant.tenant_id,
        org_id=org.org_id,
        business_unit_name="NL BU",
    )
    session.add(bu)
    await session.flush()

    div = DimDivision(
        tenant_id=tenant.tenant_id,
        business_unit_id=bu.business_unit_id,
        division_name="NL Div",
    )
    session.add(div)
    await session.flush()

    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"nlv-{uid}@example.com",
        password_hash=hash_password("secret"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="viewer"))

    session.add(
        FactRevenue(
            tenant_id=tenant.tenant_id,
            amount=Decimal("50.0000"),
            currency_code="USD",
            revenue_date=date(2026, 7, 15),
            org_id=org.org_id,
            business_unit_id=bu.business_unit_id,
            division_id=div.division_id,
            source_system="test",
            external_id=f"nlv-{uid}-1",
            batch_id=None,
        )
    )
    await session.flush()

    token = create_access_token(subject=str(user.user_id))
    return token, str(org.org_id)


class _SettingsNL:
    ENABLE_NL_QUERY = True
    QUERY_TIMEOUT_SECONDS = 60
    OPENAI_API_KEY = "test-key"
    OPENAI_MODEL = "gpt-4o-mini"


class _SettingsOff:
    ENABLE_NL_QUERY = False
    QUERY_TIMEOUT_SECONDS = 60
    OPENAI_API_KEY = None
    OPENAI_MODEL = "gpt-4o-mini"


def _patch_nl_settings(monkeypatch: pytest.MonkeyPatch, settings_cls: type) -> None:
    """NL feature flag (deps) + query engine service settings."""
    monkeypatch.setattr("app.core.deps.get_settings", lambda: settings_cls())
    monkeypatch.setattr("app.services.query_engine.service.get_settings", lambda: settings_cls())


@pytest.mark.asyncio
async def test_nl_query_completed_with_mocked_llm(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_llm(_q: str) -> dict:
        return {
            "needs_clarification": False,
            "intent": "rollup",
            "hierarchy": "bu",
            "revenue_date_from": "2026-07-01",
            "revenue_date_to": "2026-09-30",
            "interpretation": "Sum of revenue by business unit for calendar Q3 2026",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _fake_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    token, org_id = await _seed_nl_user(db_session)

    r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "Q3 2026 revenue by business unit",
            "org_id": org_id,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "completed"
    assert "business_unit_name" in data["columns"]
    assert len(data["rows"]) >= 1


@pytest.mark.asyncio
async def test_nl_query_resolves_named_business_unit_from_question(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BU-scoped questions must resolve dim_business_unit, not only dim_customer / dim_organization."""

    async def _fake_llm(_q: str) -> dict:
        return {
            "needs_clarification": False,
            "intent": "rollup",
            "hierarchy": "bu",
            "customer_name": "NL BU",
            "revenue_date_from": "2026-07-01",
            "revenue_date_to": "2026-09-30",
            "interpretation": "Revenue for named BU",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _fake_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    token, org_id = await _seed_nl_user(db_session)

    r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "overall growth of the BU NL BU",
            "org_id": org_id,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "completed"
    assert len(data["rows"]) == 1
    assert data["rows"][0]["business_unit_name"] == "NL BU"


@pytest.mark.asyncio
async def test_nl_query_disabled_returns_403(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_nl_settings(monkeypatch, _SettingsOff)

    token, org_id = await _seed_nl_user(db_session)

    r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "test", "org_id": org_id},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_story_3_1_nl_rollup_matches_analytics_api(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolved NL execution uses analytics service — same numbers as GET /analytics/revenue/rollup."""
    async def _fake_llm(_q: str) -> dict:
        return {
            "needs_clarification": False,
            "intent": "rollup",
            "hierarchy": "bu",
            "revenue_date_from": "2026-07-01",
            "revenue_date_to": "2026-09-30",
            "interpretation": "BU rollup Q3 2026",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _fake_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    token, org_id = await _seed_nl_user(db_session)

    nl_r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "revenue by BU Q3 2026", "org_id": org_id},
    )
    assert nl_r.status_code == 200, nl_r.text
    nl_data = nl_r.json()
    assert nl_data["status"] == "completed"

    ar = await async_client.get(
        "/api/v1/analytics/revenue/rollup",
        params={
            "hierarchy": "bu",
            "revenue_date_from": "2026-07-01",
            "revenue_date_to": "2026-09-30",
            "org_id": org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ar.status_code == 200
    api_rows = {row["business_unit_name"]: row["revenue"] for row in ar.json()["rows"]}
    nl_rows = {row["business_unit_name"]: row["total_revenue"] for row in nl_data["rows"]}
    assert nl_rows == api_rows


@pytest.mark.asyncio
async def test_story_3_2_invalid_plan_returns_400_not_stack_trace(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _bad_llm(_q: str) -> dict:
        return {
            "needs_clarification": False,
            "intent": "unsupported_intent",
            "hierarchy": "org",
            "revenue_date_from": "2026-01-01",
            "revenue_date_to": "2026-01-31",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _bad_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    token, org_id = await _seed_nl_user(db_session)
    r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "anything", "org_id": org_id},
    )
    assert r.status_code == 400
    body = r.json()
    assert "detail" in body
    assert "QUERY_UNSAFE" in str(body) or "error" in body


@pytest.mark.asyncio
async def test_story_3_3_disambiguation_round_trip(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ambiguous quarter without year → needs_clarification; follow-up completes without guessing."""
    calls: list[str] = []

    async def _fake_llm(q: str) -> dict:
        calls.append(q)
        if len(calls) == 1:
            return {
                "needs_clarification": True,
                "clarification_prompts": [
                    {
                        "prompt_id": "fiscal_year",
                        "text": "Which calendar year for Q3?",
                        "choices": [{"id": "2026", "label": "Calendar year 2026"}],
                    }
                ],
                "intent": "rollup",
                "hierarchy": "bu",
                "calendar_quarter": 3,
                "interpretation": "Q3 revenue by BU (year needed)",
            }
        return {
            "needs_clarification": False,
            "intent": "rollup",
            "hierarchy": "bu",
            "revenue_date_from": "2026-07-01",
            "revenue_date_to": "2026-09-30",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _fake_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    token, org_id = await _seed_nl_user(db_session)

    r1 = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Q3 revenue by business unit", "org_id": org_id},
    )
    assert r1.status_code == 200, r1.text
    first = r1.json()
    assert first["status"] == "needs_clarification"
    assert first.get("disambiguation", {}).get("token")
    assert first.get("questions")

    token_plain = first["disambiguation"]["token"]
    r2 = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "Q3 revenue by business unit",
            "org_id": org_id,
            "disambiguation_token": token_plain,
            "clarifications": [{"prompt_id": "fiscal_year", "choice": "2026"}],
        },
    )
    assert r2.status_code == 200, r2.text
    second = r2.json()
    assert second["status"] == "completed"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_explicit_month_year_skips_fiscal_year_clarification(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User text like mar'26 is resolved to a calendar month; do not prompt for FY."""

    async def _fake_llm(_q: str) -> dict:
        return {
            "needs_clarification": True,
            "clarification_prompts": [
                {
                    "prompt_id": "fiscal_year",
                    "text": "Please specify the fiscal year for March.",
                    "choices": [{"id": "2025", "label": "FY 2025"}, {"id": "2026", "label": "FY 2026"}],
                }
            ],
            "intent": "rollup",
            "hierarchy": "bu",
            "calendar_quarter": 1,
            "interpretation": "March (year unclear)",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _fake_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    token, org_id = await _seed_nl_user(db_session)

    r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "What was Mar'26 revenue by business unit",
            "org_id": org_id,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_nl_question_with_customer_phrase_resolves_dim_customer(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Named customer in plain language maps to dim_customer — not a generic org rollup."""

    async def _fake_llm(_q: str) -> dict:
        return {
            "needs_clarification": False,
            "intent": "rollup",
            "hierarchy": "org",
            "revenue_date_from": "2026-03-01",
            "revenue_date_to": "2026-03-31",
            "interpretation": "rollup",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _fake_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    token, org_id = await _seed_nl_user_with_who_customer(db_session)

    r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "What was the Mar'26 revenue for World health Orgnization",
            "org_id": org_id,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "completed"
    assert "customer_name" in data["columns"]
    assert len(data["rows"]) == 1
    assert "World Health Organization" in data["rows"][0]["customer_name"]
    assert data["rows"][0]["total_revenue"] == "1292150.9400"


@pytest.mark.asyncio
async def test_story_3_4_query_audit_requires_authentication(
    async_client: AsyncClient,
) -> None:
    r = await async_client.get("/api/v1/query/audit")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_story_3_4_viewer_cannot_list_audit(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, _org_id = await _seed_viewer_nl_user(db_session)
    r = await async_client.get(
        "/api/v1/query/audit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_story_3_4_audit_detail_includes_resolved_plan_after_success(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.semantic_layer import load_semantic_bundle

    async def _fake_llm(_q: str) -> dict:
        return {
            "needs_clarification": False,
            "intent": "rollup",
            "hierarchy": "bu",
            "revenue_date_from": "2026-07-01",
            "revenue_date_to": "2026-09-30",
            "interpretation": "test audit",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _fake_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    cid = "12345678-1234-5678-1234-567812345678"
    token, org_id = await _seed_nl_user(db_session)

    r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Correlation-Id": cid,
        },
        json={"question": "revenue by BU", "org_id": org_id},
    )
    assert r.status_code == 200, r.text
    qid = r.json()["query_id"]

    d = await async_client.get(
        f"/api/v1/query/audit/{qid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert d.status_code == 200
    payload = d.json()
    assert payload["natural_query"]
    assert payload["resolved_plan"]["kind"] == "structured_summary"
    assert payload["resolved_plan"].get("safe_sql_fingerprint", "").startswith("sha256:")
    assert str(payload["correlation_id"]) == cid
    assert payload.get("semantic_version_id") is not None

    ver = await async_client.get(
        "/api/v1/semantic-layer/version",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ver.status_code == 200
    assert ver.json()["content_sha256"] == load_semantic_bundle().content_sha256


@pytest.mark.asyncio
async def test_nl_org_fallback_when_llm_mislabels_company_as_business_unit(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the model puts an organization name in business_unit_name, resolve dim_organization."""

    async def _fake_llm(_q: str) -> dict:
        return {
            "needs_clarification": False,
            "intent": "rollup",
            "hierarchy": "bu",
            "business_unit_name": "NL Org",
            "revenue_date_from": "2026-01-01",
            "revenue_date_to": "2026-12-31",
            "interpretation": "FY revenue (mislabeled as BU)",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _fake_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    token, org_id = await _seed_nl_user(db_session)

    r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "revenue of NL Org overall this fiscal year",
            "org_id": org_id,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "completed"
    assert "org_name" in data["columns"]
    assert len(data["rows"]) >= 1
    assert data["rows"][0]["org_name"] == "NL Org"


@pytest.mark.asyncio
async def test_nl_variance_comment_returns_stored_narrative(
    phase3_tables: None,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """variance_comment intent reads revenue_variance_comment (no numeric rollup)."""

    async def _fake_llm(_q: str) -> dict:
        return {
            "needs_clarification": False,
            "intent": "variance_comment",
            "hierarchy": "customer",
            "customer_name": "World Health Organization",
            "variance_revenue_month": "2026-04-01",
            "interpretation": "MoM variance narrative for April 2026",
        }

    monkeypatch.setattr("app.services.query_engine.service.complete_nl_plan", _fake_llm)
    _patch_nl_settings(monkeypatch, _SettingsNL)

    token, org_id = await _seed_nl_user_with_who_customer(db_session)

    org_uuid = uuid.UUID(org_id)
    org_row = await db_session.scalar(select(DimOrganization).where(DimOrganization.org_id == org_uuid))
    cust_row = await db_session.scalar(
        select(DimCustomer).where(
            DimCustomer.org_id == org_uuid,
            DimCustomer.customer_name == "World Health Organization",
        )
    )
    assert org_row is not None and cust_row is not None

    db_session.add(
        RevenueVarianceComment(
            tenant_id=org_row.tenant_id,
            org_id=org_row.org_id,
            customer_id=cust_row.customer_id,
            revenue_month=date(2026, 4, 1),
            business_unit_id=None,
            division_id=None,
            comment_text="Milestone billing shifted into April.",
        )
    )
    await db_session.flush()

    r = await async_client.post(
        "/api/v1/query/natural-language",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "Why did revenue deviate from March 2026 to April 2026 for WHO",
            "org_id": org_id,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "completed"
    assert "variance_comment" in data["columns"]
    assert len(data["rows"]) == 1
    assert data["rows"][0]["variance_comment"] == "Milestone billing shifted into April."
    assert data["rows"][0]["revenue_month"] == "2026-04-01"
