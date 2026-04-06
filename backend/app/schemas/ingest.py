"""Ingestion API DTOs."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IngestErrorItem(BaseModel):
    row: int | None = None
    column: str | None = None
    message: str


class IngestErrorLog(BaseModel):
    errors: list[IngestErrorItem] = Field(default_factory=list)


class UploadSyncSuccessResponse(BaseModel):
    batch_id: uuid.UUID
    status: str
    total_rows: int | None = None
    loaded_rows: int = 0
    period_start: date | None = None
    period_end: date | None = None


class UploadSyncFailedResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    batch_id: uuid.UUID
    status: str = "failed"
    total_rows: int | None = None
    loaded_rows: int = 0
    error_log: dict[str, Any]


class UploadAsyncResponse(BaseModel):
    batch_id: uuid.UUID
    status: str = "pending"
    message: str = "Processing in background"


class BatchListItem(BaseModel):
    batch_id: uuid.UUID
    source_system: str
    filename: str | None
    status: str
    total_rows: int | None
    loaded_rows: int
    error_rows: int
    started_at: datetime
    completed_at: datetime | None


class BatchListResponse(BaseModel):
    items: list[BatchListItem]
    next_cursor: str | None = None


class BatchDetailResponse(BaseModel):
    batch_id: uuid.UUID
    tenant_id: uuid.UUID
    source_system: str
    filename: str | None
    storage_key: str | None
    status: str
    total_rows: int | None
    loaded_rows: int
    error_rows: int
    error_log: dict[str, Any] | None
    period_start: date | None
    period_end: date | None
    scope_org_id: uuid.UUID | None
    initiated_by: uuid.UUID | None
    started_at: datetime
    completed_at: datetime | None
