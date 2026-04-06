"""Phase 4 — HubSpot connection, sync, mapping, conflicts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.core.database import Base


class HubspotConnection(Base):
    __tablename__ = "hubspot_connection"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_hubspot_connection_tenant"),
        Index("idx_hubspot_connection_status", "tenant_id", "status"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    hubspot_portal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_token_bundle: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes_granted: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_token_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class HubspotSyncCursor(Base):
    __tablename__ = "hubspot_sync_cursor"
    __table_args__ = (UniqueConstraint("tenant_id", "object_type", name="uq_hubspot_sync_cursor_tenant_object"),)

    cursor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cursor_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class HubspotIdMapping(Base):
    __tablename__ = "hubspot_id_mapping"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "hubspot_object_type",
            "hubspot_object_id",
            name="uq_hubspot_id_mapping_object",
        ),
        Index("idx_hubspot_mapping_tenant_status", "tenant_id", "status"),
    )

    mapping_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    hubspot_object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    hubspot_object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_customer.customer_id", ondelete="SET NULL"), nullable=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_organization.org_id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class IntegrationSyncRun(Base):
    __tablename__ = "integration_sync_run"
    __table_args__ = (Index("idx_integration_sync_run_tenant_started", "tenant_id", "started_at"),)

    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    integration_code: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rows_fetched: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rows_loaded: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rows_failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RevenueSourceConflict(Base):
    __tablename__ = "revenue_source_conflict"
    __table_args__ = (
        Index("idx_revenue_conflict_tenant_status", "tenant_id", "status"),
        Index("idx_revenue_conflict_detected", "tenant_id", "detected_at"),
    )

    conflict_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    reconciliation_key: Mapped[str] = mapped_column(String(512), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_customer.customer_id"), nullable=True
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    excel_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    hubspot_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    excel_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("fact_revenue.revenue_id"), nullable=True
    )
    hubspot_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("fact_revenue.revenue_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class HubspotDealStaging(Base):
    __tablename__ = "hubspot_deal_staging"
    __table_args__ = (
        Index("idx_hubspot_staging_run", "sync_run_id"),
        Index("idx_hubspot_staging_deal", "tenant_id", "hubspot_deal_id"),
    )

    staging_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("integration_sync_run.sync_run_id", ondelete="CASCADE"), nullable=False
    )
    hubspot_deal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
