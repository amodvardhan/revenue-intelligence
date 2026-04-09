"""Read-only dimension endpoints (Phase 1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.dimensions import DimBusinessUnit, DimDivision, DimOrganization
from app.models.tenant import User
from app.services.access_scope import accessible_org_ids

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


class BusinessUnitItem(BaseModel):
    business_unit_id: UUID
    business_unit_name: str
    org_id: UUID


class BusinessUnitListResponse(BaseModel):
    items: list[BusinessUnitItem]


@router.get(
    "/business-units",
    response_model=BusinessUnitListResponse,
    summary="List business units for an organization",
)
async def list_business_units(
    org_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BusinessUnitListResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    res = await session.execute(
        select(DimBusinessUnit).where(
            DimBusinessUnit.tenant_id == user.tenant_id,
            DimBusinessUnit.org_id == org_id,
            DimBusinessUnit.is_active.is_(True),
        ).order_by(DimBusinessUnit.business_unit_name)
    )
    items = [
        BusinessUnitItem(
            business_unit_id=b.business_unit_id,
            business_unit_name=b.business_unit_name,
            org_id=b.org_id,
        )
        for b in res.scalars().all()
    ]
    return BusinessUnitListResponse(items=items)


class DivisionItem(BaseModel):
    division_id: UUID
    division_name: str
    business_unit_id: UUID


class DivisionListResponse(BaseModel):
    items: list[DivisionItem]


@router.get(
    "/divisions",
    response_model=DivisionListResponse,
    summary="List divisions under a business unit",
)
async def list_divisions(
    business_unit_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DivisionListResponse:
    bu = await session.scalar(
        select(DimBusinessUnit).where(
            DimBusinessUnit.business_unit_id == business_unit_id,
            DimBusinessUnit.tenant_id == user.tenant_id,
        )
    )
    if bu is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Business unit not found", "details": None}},
        )
    accessible = await accessible_org_ids(session, user.user_id)
    if bu.org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    res = await session.execute(
        select(DimDivision).where(
            DimDivision.tenant_id == user.tenant_id,
            DimDivision.business_unit_id == business_unit_id,
            DimDivision.is_active.is_(True),
        ).order_by(DimDivision.division_name)
    )
    items = [
        DivisionItem(
            division_id=d.division_id,
            division_name=d.division_name,
            business_unit_id=d.business_unit_id,
        )
        for d in res.scalars().all()
    ]
    return DivisionListResponse(items=items)
