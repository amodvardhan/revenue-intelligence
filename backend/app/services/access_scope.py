"""Org and BU access helpers — must stay aligned with RLS on fact_revenue."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import UserBusinessUnitAccess, UserOrgRole


async def accessible_org_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    res = await session.execute(select(UserOrgRole.org_id).where(UserOrgRole.user_id == user_id))
    return set(res.scalars().all())


async def business_unit_scope(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[str, list[uuid.UUID]]:
    """Return (`org_wide` | `restricted`, allowed BU ids). Empty list means org-wide."""
    res = await session.execute(
        select(UserBusinessUnitAccess.business_unit_id).where(
            UserBusinessUnitAccess.user_id == user_id
        )
    )
    bu_ids = list(res.scalars().all())
    if not bu_ids:
        return "org_wide", []
    return "restricted", bu_ids
