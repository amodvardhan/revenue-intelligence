"""Org-scoped projects (dim_project)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import PROJECT_WRITE_ROLES, get_current_user, org_role_allowed
from app.models.dimensions import DimCustomer, DimProject
from app.models.tenant import User
from app.schemas.project import CreateProjectBody, ProjectListResponse, ProjectRow
from app.services.access_scope import accessible_org_ids

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects for an organization",
)
async def list_projects(
    org_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    accessible = await accessible_org_ids(session, user.user_id)
    if org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    res = await session.execute(
        select(DimProject)
        .where(DimProject.tenant_id == user.tenant_id, DimProject.org_id == org_id)
        .order_by(DimProject.project_name)
    )
    items = [
        ProjectRow(
            project_id=p.project_id,
            org_id=p.org_id,
            customer_id=p.customer_id,
            project_name=p.project_name,
            project_code=p.project_code,
            is_active=p.is_active,
        )
        for p in res.scalars().all()
    ]
    return ProjectListResponse(items=items)


@router.post(
    "",
    response_model=ProjectRow,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(
    body: CreateProjectBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectRow:
    accessible = await accessible_org_ids(session, user.user_id)
    if body.org_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No access to organization", "details": None}},
        )
    if not await org_role_allowed(session, user.user_id, body.org_id, PROJECT_WRITE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Insufficient role to create projects", "details": None}},
        )

    if body.customer_id is not None:
        cust = await session.scalar(
            select(DimCustomer).where(
                DimCustomer.customer_id == body.customer_id,
                DimCustomer.tenant_id == user.tenant_id,
                DimCustomer.org_id == body.org_id,
            )
        )
        if cust is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Customer not found for this organization", "details": None}},
            )

    row = DimProject(
        tenant_id=user.tenant_id,
        org_id=body.org_id,
        customer_id=body.customer_id,
        project_name=body.project_name.strip(),
        project_code=(body.project_code.strip() if body.project_code else None) or None,
        is_active=True,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ProjectRow(
        project_id=row.project_id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        project_name=row.project_name,
        project_code=row.project_code,
        is_active=row.is_active,
    )
