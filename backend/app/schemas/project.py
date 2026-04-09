"""Projects (dim_project) — org-scoped engagements."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ProjectRow(BaseModel):
    project_id: UUID
    org_id: UUID
    customer_id: UUID | None
    project_name: str
    project_code: str | None
    is_active: bool


class ProjectListResponse(BaseModel):
    items: list[ProjectRow]


class CreateProjectBody(BaseModel):
    org_id: UUID
    project_name: str = Field(min_length=1, max_length=255)
    project_code: str | None = Field(None, max_length=100)
    customer_id: UUID | None = None
