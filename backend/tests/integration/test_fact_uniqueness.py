"""Database constraint: duplicate (source_system, external_id) rejected."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import FactRevenue
from app.models.tenant import Tenant


@pytest.mark.asyncio
async def test_duplicate_external_id_same_source_fails(db_session: AsyncSession) -> None:
    tenant = Tenant(name="Unique Test")
    db_session.add(tenant)
    await db_session.flush()

    oid = uuid4()
    from app.models.dimensions import DimOrganization

    org = DimOrganization(tenant_id=tenant.tenant_id, org_name="O")
    db_session.add(org)
    await db_session.flush()

    ext = "dup-key-1"
    first = FactRevenue(
        tenant_id=tenant.tenant_id,
        amount=Decimal("1.0000"),
        currency_code="USD",
        revenue_date=date(2026, 1, 1),
        org_id=org.org_id,
        source_system="excel",
        external_id=ext,
        batch_id=None,
    )
    db_session.add(first)
    await db_session.flush()

    duplicate = FactRevenue(
        tenant_id=tenant.tenant_id,
        amount=Decimal("2.0000"),
        currency_code="USD",
        revenue_date=date(2026, 1, 1),
        org_id=org.org_id,
        source_system="excel",
        external_id=ext,
        batch_id=None,
    )
    async with db_session.begin_nested():
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            await db_session.flush()
