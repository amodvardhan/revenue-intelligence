"""soft_delete_facts_in_scope marks rows deleted (uses flush-commit session)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimOrganization
from app.models.facts import FactRevenue
from app.models.tenant import Tenant
from app.services.ingestion.overlap import soft_delete_facts_in_scope


@pytest.mark.asyncio
async def test_soft_delete_sets_is_deleted(db_session_with_flush_commit: AsyncSession) -> None:
    session = db_session_with_flush_commit
    tenant = Tenant(name=f"sd-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="SD")
    session.add(org)
    await session.flush()

    fact = FactRevenue(
        tenant_id=tenant.tenant_id,
        amount=Decimal("1.0000"),
        currency_code="USD",
        revenue_date=date(2026, 2, 1),
        org_id=org.org_id,
        source_system="test",
        external_id=f"sd-{uuid4().hex}",
        batch_id=None,
        is_deleted=False,
    )
    session.add(fact)
    await session.flush()

    await soft_delete_facts_in_scope(
        session,
        tenant_id=tenant.tenant_id,
        org_id=org.org_id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
    )
    await session.flush()

    row = (await session.execute(select(FactRevenue.is_deleted).where(FactRevenue.revenue_id == fact.revenue_id))).scalar_one()
    assert row is True
