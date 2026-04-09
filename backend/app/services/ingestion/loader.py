"""Resolve dimensions and insert fact rows in one transaction."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import (
    DimBusinessUnit,
    DimCustomer,
    DimDivision,
    DimRevenueType,
)
from app.models.facts import FactRevenue
from app.services.ingestion.validator import ValidatedRow


class DimensionResolveError(Exception):
    """Raised when a name in Excel cannot be resolved (e.g. division without BU)."""


async def _ensure_bu(
    session: AsyncSession,
    tenant_id: UUID,
    org_id: UUID,
    name: str | None,
    cache: dict[tuple[UUID, UUID, str], UUID],
) -> UUID | None:
    if not name:
        return None
    key = (tenant_id, org_id, name)
    if key in cache:
        return cache[key]
    stmt = select(DimBusinessUnit.business_unit_id).where(
        DimBusinessUnit.tenant_id == tenant_id,
        DimBusinessUnit.org_id == org_id,
        DimBusinessUnit.business_unit_name == name,
        DimBusinessUnit.is_active.is_(True),
    )
    bid = (await session.execute(stmt)).scalar_one_or_none()
    if bid is None:
        row = DimBusinessUnit(
            tenant_id=tenant_id,
            org_id=org_id,
            business_unit_name=name,
        )
        session.add(row)
        await session.flush()
        bid = row.business_unit_id
    cache[key] = bid
    return bid


async def _ensure_division(
    session: AsyncSession,
    tenant_id: UUID,
    business_unit_id: UUID | None,
    name: str | None,
    cache: dict[tuple[UUID, UUID, str], UUID],
) -> UUID | None:
    if not name:
        return None
    if business_unit_id is None:
        raise DimensionResolveError("division requires a business_unit")
    key = (tenant_id, business_unit_id, name)
    if key in cache:
        return cache[key]
    stmt = select(DimDivision.division_id).where(
        DimDivision.tenant_id == tenant_id,
        DimDivision.business_unit_id == business_unit_id,
        DimDivision.division_name == name,
        DimDivision.is_active.is_(True),
    )
    did = (await session.execute(stmt)).scalar_one_or_none()
    if did is None:
        row = DimDivision(
            tenant_id=tenant_id,
            business_unit_id=business_unit_id,
            division_name=name,
        )
        session.add(row)
        await session.flush()
        did = row.division_id
    cache[key] = did
    return did


async def _ensure_customer(
    session: AsyncSession,
    tenant_id: UUID,
    org_id: UUID,
    name: str | None,
    cache: dict[tuple[UUID, str], UUID],
    name_common: str | None = None,
) -> UUID | None:
    if not name:
        return None
    key = (tenant_id, name)
    if key in cache:
        return cache[key]
    stmt = (
        select(DimCustomer.customer_id)
        .where(
            DimCustomer.tenant_id == tenant_id,
            DimCustomer.is_active.is_(True),
            DimCustomer.customer_name == name,
        )
        .limit(1)
    )
    cid = (await session.execute(stmt)).scalar_one_or_none()
    common_val = (name_common.strip() if name_common else "") or name
    if cid is None:
        row = DimCustomer(
            tenant_id=tenant_id,
            customer_name=name,
            customer_name_common=common_val,
            org_id=org_id,
        )
        session.add(row)
        await session.flush()
        cid = row.customer_id
    cache[key] = cid
    return cid


async def _ensure_revenue_type(
    session: AsyncSession,
    tenant_id: UUID,
    name: str | None,
    cache: dict[tuple[UUID, str], UUID],
) -> UUID | None:
    if not name:
        return None
    key = (tenant_id, name)
    if key in cache:
        return cache[key]
    stmt = select(DimRevenueType.revenue_type_id).where(
        DimRevenueType.tenant_id == tenant_id,
        DimRevenueType.revenue_type_name == name,
        DimRevenueType.is_active.is_(True),
    )
    rid = (await session.execute(stmt)).scalar_one_or_none()
    if rid is None:
        row = DimRevenueType(tenant_id=tenant_id, revenue_type_name=name)
        session.add(row)
        await session.flush()
        rid = row.revenue_type_id
    cache[key] = rid
    return rid


async def insert_revenue_facts(
    session: AsyncSession,
    *,
    batch_id: UUID,
    tenant_id: UUID,
    org_id: UUID,
    currency_code: str,
    validated_rows: list[ValidatedRow],
) -> int:
    """Insert fact rows; creates missing dimension rows for names in the file. Returns loaded count."""
    bu_cache: dict[tuple[UUID, UUID, str], UUID] = {}
    div_cache: dict[tuple[UUID, UUID, str], UUID] = {}
    cust_cache: dict[tuple[UUID, str], UUID] = {}
    rt_cache: dict[tuple[UUID, str], UUID] = {}

    count = 0
    for row in validated_rows:
        bu_id = await _ensure_bu(session, tenant_id, org_id, row.business_unit, bu_cache)
        div_id = await _ensure_division(session, tenant_id, bu_id, row.division, div_cache)
        cust_id = await _ensure_customer(
            session,
            tenant_id,
            org_id,
            row.customer,
            cust_cache,
            name_common=row.customer_name_common,
        )
        rt_id = await _ensure_revenue_type(session, tenant_id, row.revenue_type, rt_cache)

        external_id = f"excel:{batch_id}:{row.row_index}"
        fact = FactRevenue(
            tenant_id=tenant_id,
            amount=row.amount,
            currency_code=currency_code,
            revenue_date=row.revenue_date,
            org_id=org_id,
            business_unit_id=bu_id,
            division_id=div_id,
            customer_id=cust_id,
            revenue_type_id=rt_id,
            source_system="excel",
            external_id=external_id,
            batch_id=batch_id,
            is_deleted=False,
        )
        session.add(fact)
        count += 1
    return count
