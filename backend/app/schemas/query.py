"""Pydantic models for Phase 3 NL query APIs."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class ClarificationItem(BaseModel):
    prompt_id: str
    choice: str


class NaturalLanguageRequest(BaseModel):
    question: str = Field(..., min_length=1)
    org_id: uuid.UUID | None = None
    disambiguation_token: str | None = None
    clarifications: list[ClarificationItem] | None = None


class SemanticVersionResponse(BaseModel):
    version_id: uuid.UUID
    version_label: str
    source_identifier: str | None
    content_sha256: str | None
    effective_from: str
    is_active: bool


class AuditListItem(BaseModel):
    log_id: uuid.UUID
    user_id: uuid.UUID | None
    natural_query: str
    status: str | None
    row_count: int | None
    execution_ms: int | None
    created_at: str
    correlation_id: uuid.UUID | None


class AuditListResponse(BaseModel):
    items: list[AuditListItem]
    next_cursor: str | None


class AuditDetailResponse(BaseModel):
    log_id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    correlation_id: uuid.UUID | None
    nl_session_id: uuid.UUID | None
    semantic_version_id: uuid.UUID | None
    natural_query: str
    resolved_plan: dict[str, Any] | None
    execution_ms: int | None
    row_count: int | None
    status: str | None
    error_message: str | None
    created_at: str
