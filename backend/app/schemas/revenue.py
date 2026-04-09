"""Pydantic models for revenue read API."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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


class MatrixMonthColumn(BaseModel):
    """Month bucket (typically first of month) for matrix header."""

    key: str
    label: str


class MatrixLine(BaseModel):
    """One visual row: value (imported) or delta (MoM, computed for display)."""

    row_type: Literal["value", "delta"]
    sr_no: int | None = None
    customer_id: UUID | None = None
    customer_legal: str = ""
    customer_common: str | None = None
    amounts: list[str]
    amounts_editable: bool = False
    variance_comments: list[str | None] | None = None
    variance_comments_editable: bool = False


class RevenueMatrixResponse(BaseModel):
    """Customer × month grid aligned to EUROPE-style workbook layout."""

    currency_code: str
    month_columns: list[MatrixMonthColumn]
    lines: list[MatrixLine]
    empty_reason: str | None = None
    matrix_scope: Literal["organization", "business_unit", "division"] = "organization"


class MatrixCellUpsertBody(BaseModel):
    """Replace the displayed total for one customer-month (optional BU/division scope)."""

    org_id: UUID
    customer_id: UUID
    revenue_month: date = Field(description="Any date in the month; normalized to month start")
    amount: str = Field(description="Decimal string; use to set or replace manual override")
    business_unit_id: UUID | None = None
    division_id: UUID | None = None


class VarianceCommentUpsertBody(BaseModel):
    """Narrative for variance on the delta into revenue_month (MoM vs prior column); optional BU/division scope."""

    org_id: UUID
    customer_id: UUID
    revenue_month: date = Field(description="Month being explained (same as matrix column after the delta)")
    comment_text: str = Field(description="Empty string removes the narrative for this scope")
    business_unit_id: UUID | None = None
    division_id: UUID | None = None


class VarianceCommentPromptItem(BaseModel):
    """DM dashboard: assigned customer month needing a variance narrative."""

    customer_id: UUID
    customer_legal: str
    revenue_month: date
    month_label: str
    mom_delta: str | None = None
    yoy_delta: str | None = None
    currency_code: str = "USD"


class VarianceCommentPromptListResponse(BaseModel):
    items: list[VarianceCommentPromptItem]
