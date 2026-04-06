"""Ingestion batch and revenue fact tables."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from app.core.database import Base


class AnalyticsRefreshMetadata(Base):
    """Phase 2: last refresh times for materialized analytics structures."""

    __tablename__ = "analytics_refresh_metadata"
    __table_args__ = (
        UniqueConstraint("tenant_id", "structure_name", name="uq_analytics_refresh_tenant_structure"),
        Index("idx_analytics_refresh_tenant", "tenant_id"),
    )

    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    structure_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_refresh_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refresh_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_completed_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingestion_batch.batch_id"),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IngestionBatch(Base):
    __tablename__ = "ingestion_batch"
    __table_args__ = (
        Index("idx_ingestion_batch_tenant_status", "tenant_id", "status"),
        Index("idx_ingestion_batch_started", "started_at"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'pending'"),
    )
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loaded_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_log: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    scope_org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dim_organization.org_id"),
        nullable=True,
    )
    replace_of_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingestion_batch.batch_id"),
        nullable=True,
    )
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    initiator: Mapped["User | None"] = relationship("User", foreign_keys=[initiated_by])
    revenue_facts: Mapped[list["FactRevenue"]] = relationship(
        "FactRevenue",
        back_populates="batch",
    )


class FactRevenue(Base):
    __tablename__ = "fact_revenue"
    __table_args__ = (
        UniqueConstraint("source_system", "external_id", name="uq_fact_revenue_source_external"),
        Index("idx_fact_revenue_date", "revenue_date"),
        Index("idx_fact_revenue_org", "tenant_id", "org_id", "revenue_date"),
        Index(
            "idx_fact_revenue_bu",
            "business_unit_id",
            "revenue_date",
            postgresql_where=text("business_unit_id IS NOT NULL"),
        ),
        Index(
            "idx_fact_revenue_division",
            "division_id",
            "revenue_date",
            postgresql_where=text("division_id IS NOT NULL"),
        ),
        Index("idx_fact_revenue_source", "source_system", "external_id"),
        Index("idx_fact_revenue_batch", "batch_id"),
    )

    revenue_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'USD'"))
    revenue_date: Mapped[date] = mapped_column(Date, nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dim_organization.org_id", ondelete="RESTRICT"),
        nullable=False,
    )
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dim_business_unit.business_unit_id", ondelete="RESTRICT"),
        nullable=True,
    )
    division_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dim_division.division_id", ondelete="RESTRICT"),
        nullable=True,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dim_customer.customer_id", ondelete="RESTRICT"),
        nullable=True,
    )
    revenue_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dim_revenue_type.revenue_type_id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    amount_reporting_currency: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    fx_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fx_rate.fx_rate_id", ondelete="SET NULL"),
        nullable=True,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingestion_batch.batch_id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
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

    batch: Mapped["IngestionBatch | None"] = relationship(back_populates="revenue_facts")
