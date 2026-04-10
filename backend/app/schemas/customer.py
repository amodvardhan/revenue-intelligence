"""Customer dimension (dim_customer) — manual create + list."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class CustomerItem(BaseModel):
    customer_id: UUID
    customer_name: str
    customer_name_common: str | None
    customer_code: str | None
    business_unit_id: UUID | None = None
    business_unit_name: str | None = None
    division_id: UUID | None = None
    division_name: str | None = None


class CustomerListResponse(BaseModel):
    items: list[CustomerItem]


class CreateCustomerBody(BaseModel):
    org_id: UUID
    customer_name: str = Field(min_length=1, max_length=255)
    customer_name_common: str | None = Field(None, max_length=255)
    customer_code: str | None = Field(None, max_length=100)
    business_unit_id: UUID | None = None
    division_id: UUID | None = None


class PatchCustomerBody(BaseModel):
    """Patch commercial hierarchy; omit a key to leave that column unchanged."""

    business_unit_id: UUID | None = None
    division_id: UUID | None = None
