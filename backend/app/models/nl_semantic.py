"""Phase 3 — semantic layer version and NL clarification sessions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant, User


class SemanticLayerVersion(Base):
    __tablename__ = "semantic_layer_version"
    __table_args__ = (Index("idx_semantic_layer_version_tenant", "tenant_id"),)

    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    source_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])


class NlQuerySession(Base):
    __tablename__ = "nl_query_session"
    __table_args__ = (
        Index("idx_nl_query_session_user_created", "user_id", "created_at"),
        Index("idx_nl_query_session_expires", "expires_at"),
    )

    nl_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    pending_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
