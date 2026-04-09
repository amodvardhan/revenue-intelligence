"""Who may write manual matrix cells: finance-style roles, or assigned delivery managers (org-wide scope)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import MATRIX_EDIT_ROLES, org_role_allowed
from app.models.phase7 import CustomerDeliveryManagerAssignment
from app.models.tenant import User


async def dm_assigned_customer_ids(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Customers for which this user is the active delivery manager in the org."""
    res = await session.execute(
        select(CustomerDeliveryManagerAssignment.customer_id).where(
            CustomerDeliveryManagerAssignment.tenant_id == tenant_id,
            CustomerDeliveryManagerAssignment.org_id == org_id,
            CustomerDeliveryManagerAssignment.delivery_manager_user_id == user_id,
            CustomerDeliveryManagerAssignment.valid_to.is_(None),
        )
    )
    return set(res.scalars().all())


async def matrix_edit_flags(
    session: AsyncSession,
    user: User,
    org_id: uuid.UUID,
) -> tuple[bool, set[uuid.UUID]]:
    """(full_editor, dm_customer_ids). Full editors use MATRIX_EDIT_ROLES; else DM set may be non-empty."""
    full = await org_role_allowed(session, user.user_id, org_id, MATRIX_EDIT_ROLES)
    if full:
        return True, set()
    dm_ids = await dm_assigned_customer_ids(
        session, tenant_id=user.tenant_id, org_id=org_id, user_id=user.user_id
    )
    return False, dm_ids


async def can_write_manual_matrix_cell(
    session: AsyncSession,
    user: User,
    org_id: uuid.UUID,
    customer_id: uuid.UUID,
    business_unit_id: uuid.UUID | None,
    division_id: uuid.UUID | None,
) -> bool:
    """DMs may only write org-wide cells (no BU/division scope) for assigned customers."""
    full, dm_ids = await matrix_edit_flags(session, user, org_id)
    if full:
        return True
    if business_unit_id is not None or division_id is not None:
        return False
    return customer_id in dm_ids
