"""End-to-end ingestion: run_ingestion + POST /ingest/uploads (commit mapped to flush in conftest)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ImportOverlapError
from app.core.security import create_access_token, hash_password
from app.models.dimensions import DimOrganization, UserOrgRole
from app.models.facts import AnalyticsRefreshMetadata, FactRevenue, IngestionBatch
from app.models.tenant import Tenant, User
from app.services.ingestion.ingestion_service import run_ingestion
from tests.support.xlsx_bytes import minimal_revenue_xlsx


async def _seed_tenant_org_user_finance(session: AsyncSession) -> tuple[Tenant, DimOrganization, User]:
    """Tenant + org + user with finance role (ingest)."""
    tenant = Tenant(name=f"e2e-{uuid4().hex[:10]}")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="E2E Org")
    session.add(org)
    await session.flush()
    uid = uuid4().hex[:12]
    user = User(
        tenant_id=tenant.tenant_id,
        email=f"e2e-{uid}@example.com",
        password_hash=hash_password("pw"),
    )
    session.add(user)
    await session.flush()
    session.add(UserOrgRole(user_id=user.user_id, org_id=org.org_id, role="finance"))
    await session.flush()
    return tenant, org, user


@pytest.mark.asyncio
async def test_run_ingestion_persists_facts(db_session_with_flush_commit: AsyncSession) -> None:
    session = db_session_with_flush_commit
    tenant, org, _user = await _seed_tenant_org_user_finance(session)
    batch = IngestionBatch(
        tenant_id=tenant.tenant_id,
        source_system="excel",
        filename="t.xlsx",
        storage_key="file://noop",
        status="pending",
    )
    session.add(batch)
    await session.flush()

    content = minimal_revenue_xlsx()
    out = await run_ingestion(
        session,
        batch_id=batch.batch_id,
        file_content=content,
        org_id=org.org_id,
        scope_org_id=None,
        period_start=None,
        period_end=None,
        replace=False,
    )
    assert out.status == "completed"
    assert out.loaded_rows == 2
    assert out.total_rows == 2

    cnt = await session.execute(
        select(func.count()).select_from(FactRevenue).where(FactRevenue.batch_id == batch.batch_id)
    )
    assert cnt.scalar_one() == 2


@pytest.mark.asyncio
async def test_run_ingestion_overlap_raises_without_replace(db_session_with_flush_commit: AsyncSession) -> None:
    session = db_session_with_flush_commit
    tenant, org, _user = await _seed_tenant_org_user_finance(session)
    content = minimal_revenue_xlsx()

    b1 = IngestionBatch(
        tenant_id=tenant.tenant_id,
        source_system="excel",
        filename="a.xlsx",
        storage_key="file://noop",
        status="pending",
    )
    session.add(b1)
    await session.flush()
    first = await run_ingestion(
        session,
        batch_id=b1.batch_id,
        file_content=content,
        org_id=org.org_id,
        scope_org_id=None,
        period_start=None,
        period_end=None,
        replace=False,
    )
    assert first.status == "completed"

    meta = await session.execute(
        select(AnalyticsRefreshMetadata).where(AnalyticsRefreshMetadata.tenant_id == tenant.tenant_id)
    )
    refresh_rows = list(meta.scalars().all())
    assert len(refresh_rows) >= 1
    names = {r.structure_name for r in refresh_rows}
    assert "mv_revenue_monthly_by_org" in names

    b2 = IngestionBatch(
        tenant_id=tenant.tenant_id,
        source_system="excel",
        filename="b.xlsx",
        storage_key="file://noop",
        status="pending",
    )
    session.add(b2)
    await session.flush()
    with pytest.raises(ImportOverlapError):
        await run_ingestion(
            session,
            batch_id=b2.batch_id,
            file_content=content,
            org_id=org.org_id,
            scope_org_id=None,
            period_start=None,
            period_end=None,
            replace=False,
        )


@pytest.mark.asyncio
async def test_run_ingestion_creates_missing_business_unit(db_session_with_flush_commit: AsyncSession) -> None:
    session = db_session_with_flush_commit
    tenant, org, _user = await _seed_tenant_org_user_finance(session)
    batch = IngestionBatch(
        tenant_id=tenant.tenant_id,
        source_system="excel",
        filename="t.xlsx",
        storage_key="file://noop",
        status="pending",
    )
    session.add(batch)
    await session.flush()

    content = minimal_revenue_xlsx(with_unknown_bu=True)
    out = await run_ingestion(
        session,
        batch_id=batch.batch_id,
        file_content=content,
        org_id=org.org_id,
        scope_org_id=None,
        period_start=None,
        period_end=None,
        replace=False,
    )
    assert out is not None
    assert out.status == "completed"
    assert out.loaded_rows == 1


@pytest.mark.asyncio
async def test_run_ingestion_corrupt_bytes_user_facing_error(db_session_with_flush_commit: AsyncSession) -> None:
    session = db_session_with_flush_commit
    tenant, org, _user = await _seed_tenant_org_user_finance(session)
    batch = IngestionBatch(
        tenant_id=tenant.tenant_id,
        source_system="excel",
        filename="bad.xlsx",
        storage_key="file://noop",
        status="pending",
    )
    session.add(batch)
    await session.flush()

    out = await run_ingestion(
        session,
        batch_id=batch.batch_id,
        file_content=b"not-a-valid-xlsx",
        org_id=org.org_id,
        scope_org_id=None,
        period_start=None,
        period_end=None,
        replace=False,
    )
    assert out.status == "failed"
    msg = str(out.error_log)
    assert "Could not read Excel file" in msg


@pytest.mark.asyncio
async def test_post_uploads_returns_row_counts(
    async_client_ingest: AsyncClient, db_session_with_flush_commit: AsyncSession
) -> None:
    session = db_session_with_flush_commit
    tenant, org, user = await _seed_tenant_org_user_finance(session)
    token = create_access_token(subject=str(user.user_id))
    content = minimal_revenue_xlsx()

    res = await async_client_ingest.post(
        "/api/v1/ingest/uploads",
        data={"org_id": str(org.org_id)},
        files={
            "file": (
                "rows.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "completed"
    assert body["loaded_rows"] == 2
    assert body["total_rows"] == 2


@pytest.mark.asyncio
async def test_post_uploads_rejects_non_excel_extension(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Valid auth + wrong extension → 400 (not 401)."""
    tenant, org, user = await _seed_tenant_org_user_finance(db_session)
    await db_session.flush()
    token = create_access_token(subject=str(user.user_id))

    res = await async_client.post(
        "/api/v1/ingest/uploads",
        data={"org_id": str(org.org_id)},
        files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
