"""Validate dim_customer business_unit_id / division_id against org and tenant."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimBusinessUnit, DimDivision


class CustomerHierarchyError(ValueError):
    """Invalid BU/division combination for the customer's organization."""


async def resolve_validated_customer_hierarchy(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_id: uuid.UUID,
    business_unit_id: uuid.UUID | None,
    division_id: uuid.UUID | None,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """
    Return (business_unit_id, division_id) after verifying tenant and org alignment.
    division_id requires business_unit_id; division must sit under that BU.
    """
    if division_id is not None and business_unit_id is None:
        raise CustomerHierarchyError("division_id requires business_unit_id")
    if business_unit_id is None:
        return None, None
    bu = await session.scalar(
        select(DimBusinessUnit).where(
            DimBusinessUnit.business_unit_id == business_unit_id,
            DimBusinessUnit.tenant_id == tenant_id,
            DimBusinessUnit.org_id == org_id,
            DimBusinessUnit.is_active.is_(True),
        )
    )
    if bu is None:
        raise CustomerHierarchyError("business_unit_id not found for this organization")
    if division_id is None:
        return business_unit_id, None
    div = await session.scalar(
        select(DimDivision).where(
            DimDivision.division_id == division_id,
            DimDivision.tenant_id == tenant_id,
            DimDivision.business_unit_id == business_unit_id,
            DimDivision.is_active.is_(True),
        )
    )
    if div is None:
        raise CustomerHierarchyError("division_id not found under the selected business unit")
    return business_unit_id, division_id
