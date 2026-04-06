"""Phase 5 — FX, forecast, cost, segments."""

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
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.core.database import Base


class FxRate(Base):
    __tablename__ = "fx_rate"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "base_currency_code",
            "quote_currency_code",
            "effective_date",
            name="uq_fx_rate_tenant_pair_date",
        ),
        Index("idx_fx_rate_tenant_effective", "tenant_id", "effective_date"),
    )

    fx_rate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    base_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    rate_source: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingestion_batch.batch_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ForecastSeries(Base):
    __tablename__ = "forecast_series"
    __table_args__ = (Index("idx_forecast_series_tenant_created", "tenant_id", "created_at"),)

    forecast_series_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    methodology: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    superseded_by_series_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("forecast_series.forecast_series_id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class FactForecast(Base):
    __tablename__ = "fact_forecast"
    __table_args__ = (
        UniqueConstraint("forecast_series_id", "external_id", name="uq_fact_forecast_series_external"),
        Index("idx_fact_forecast_series_period", "forecast_series_id", "period_start"),
        Index("idx_fact_forecast_tenant", "tenant_id", "period_start"),
    )

    forecast_fact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    forecast_series_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("forecast_series.forecast_series_id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_organization.org_id", ondelete="RESTRICT"), nullable=False
    )
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_business_unit.business_unit_id", ondelete="RESTRICT"), nullable=True
    )
    division_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_division.division_id", ondelete="RESTRICT"), nullable=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_customer.customer_id", ondelete="RESTRICT"), nullable=True
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingestion_batch.batch_id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class FactCost(Base):
    __tablename__ = "fact_cost"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_system", "external_id", name="uq_fact_cost_tenant_source_external"),
        Index("idx_fact_cost_tenant_date", "tenant_id", "cost_date"),
        Index("idx_fact_cost_org", "org_id", "cost_date"),
    )

    cost_fact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    cost_date: Mapped[date] = mapped_column(Date, nullable=False)
    cost_category: Mapped[str] = mapped_column(String(100), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_organization.org_id", ondelete="RESTRICT"), nullable=False
    )
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_business_unit.business_unit_id", ondelete="RESTRICT"), nullable=True
    )
    division_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_division.division_id", ondelete="RESTRICT"), nullable=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_customer.customer_id", ondelete="RESTRICT"), nullable=True
    )
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingestion_batch.batch_id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CostAllocationRule(Base):
    __tablename__ = "cost_allocation_rule"
    __table_args__ = (Index("idx_cost_alloc_rule_tenant_effective", "tenant_id", "effective_from"),)

    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    basis: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    superseded_by_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cost_allocation_rule.rule_id", ondelete="SET NULL"), nullable=True
    )


class SegmentDefinition(Base):
    __tablename__ = "segment_definition"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_segment_definition_tenant_name"),)

    segment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_organization.org_id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class SegmentMembership(Base):
    __tablename__ = "segment_membership"
    __table_args__ = (
        Index("idx_segment_membership_segment", "segment_id", "segment_version"),
        Index("idx_segment_membership_customer", "customer_id"),
    )

    membership_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), nullable=False
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("segment_definition.segment_id", ondelete="CASCADE"), nullable=False
    )
    segment_version: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_customer.customer_id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
