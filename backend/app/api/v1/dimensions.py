"""Read-only dimension endpoints (Phase 1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.dimensions import DimOrganization
from app.models.tenant import User

router = APIRouter(tags=["dimensions"])


class OrganizationItem(BaseModel):
    org_id: UUID
    org_name: str
    parent_org_id: UUID | None
    is_active: bool


class OrganizationListResponse(BaseModel):
    items: list[OrganizationItem]


@router.get(
    "/organizations",
    response_model=OrganizationListResponse,
    summary="List organizations for tenant",
)
async def list_organizations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrganizationListResponse:
    res = await session.execute(
        select(DimOrganization).where(DimOrganization.tenant_id == user.tenant_id)
    )
    items = [
        OrganizationItem(
            org_id=o.org_id,
            org_name=o.org_name,
            parent_org_id=o.parent_org_id,
            is_active=o.is_active,
        )
        for o in res.scalars().all()
    ]
    return OrganizationListResponse(items=items)
