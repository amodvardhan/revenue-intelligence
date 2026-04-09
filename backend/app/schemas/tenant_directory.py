"""Tenant directory — create and list users (e.g. delivery managers)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrgRoleItem(BaseModel):
    org_id: UUID
    org_name: str
    role: str


class TenantUserItem(BaseModel):
    user_id: UUID
    email: str
    is_active: bool
    org_roles: list[OrgRoleItem]


class TenantUserListResponse(BaseModel):
    items: list[TenantUserItem]


class CreateTenantUserBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    org_id: UUID
    role: Literal[
        "viewer",
        "cxo",
        "bu_head",
        "finance",
        "admin",
        "it_admin",
        "account_manager",
        "delivery_manager",
    ]


class CreateTenantUserResponse(BaseModel):
    user_id: UUID
    email: str
