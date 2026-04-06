"""Auth request/response DTOs."""

from __future__ import annotations

import uuid

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    tenant_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class MeRole(BaseModel):
    org_id: uuid.UUID
    role: str


class BusinessUnitScope(BaseModel):
    mode: Literal["org_wide", "restricted"]
    business_unit_ids: list[uuid.UUID]


class MeResponse(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    roles: list[MeRole]
    business_unit_scope: BusinessUnitScope
    primary_auth: str | None = None
    sso_required_for_user: bool | None = None
