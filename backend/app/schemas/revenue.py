"""Pydantic models for revenue read API."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class RevenueRow(BaseModel):
    """Single fact row — amounts as decimal strings per API contract."""

    revenue_id: UUID
    amount: str
    currency_code: str
    revenue_date: date
    org_id: UUID
    business_unit_id: UUID | None
    division_id: UUID | None
    customer_id: UUID | None
    revenue_type_id: UUID | None
    source_system: str
    batch_id: UUID | None


class RevenueListResponse(BaseModel):
    items: list[RevenueRow]
    next_cursor: str | None = None
