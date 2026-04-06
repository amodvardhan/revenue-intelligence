"""Loader dimension resolution — Excel ingest creates missing dimension rows."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimOrganization
from app.models.tenant import Tenant
from app.services.ingestion.loader import DimensionResolveError, _ensure_bu, _ensure_division


async def _tenant_org(session: AsyncSession) -> tuple[Tenant, DimOrganization]:
    tenant = Tenant(name=f"ld-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="L")
    session.add(org)
    await session.flush()
    return tenant, org


@pytest.mark.asyncio
async def test_ensure_business_unit_creates_when_missing(db_session: AsyncSession) -> None:
    tenant, org = await _tenant_org(db_session)
    cache: dict[tuple[UUID, UUID, str], UUID] = {}
    bu_id = await _ensure_bu(db_session, tenant.tenant_id, org.org_id, "NEW_BU", cache)
    assert bu_id is not None
    same = await _ensure_bu(db_session, tenant.tenant_id, org.org_id, "NEW_BU", cache)
    assert same == bu_id


@pytest.mark.asyncio
async def test_ensure_division_requires_business_unit(db_session: AsyncSession) -> None:
    tenant, org = await _tenant_org(db_session)
    cache: dict = {}
    with pytest.raises(DimensionResolveError, match="division requires a business_unit"):
        await _ensure_division(db_session, tenant.tenant_id, None, "D1", cache)
