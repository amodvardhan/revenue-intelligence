"""Phase 7 — variance detection, workbook templates, notification outbox."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
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


class VarianceDetectionRule(Base):
    """Per-tenant thresholds and comparison type for variance detection."""

    __tablename__ = "variance_detection_rule"
    __table_args__ = (
        CheckConstraint(
            "comparison_type IN ('mom', 'yoy', 'vs_goal')",
            name="ck_variance_rule_comparison_type",
        ),
        Index("idx_variance_rule_tenant", "tenant_id"),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    comparison_type: Mapped[str] = mapped_column(String(50), nullable=False)
    min_abs_delta: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    min_pct: Mapped[object | None] = mapped_column(Numeric(18, 6), nullable=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_organization.org_id", ondelete="SET NULL"), nullable=True
    )
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dim_business_unit.business_unit_id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RevenueVarianceCase(Base):
    """One row per detected discrepancy (idempotent natural key per D4)."""

    __tablename__ = "revenue_variance_case"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="ck_variance_case_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'explained', 'dismissed')",
            name="ck_variance_case_status",
        ),
        UniqueConstraint(
            "tenant_id",
            "rule_id",
            "customer_id",
            "period_month",
            "division_id",
            name="uq_variance_case_natural_key",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_variance_case_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("idx_variance_case_tenant_customer_period", "tenant_id", "customer_id", "period_month"),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_organization.org_id", ondelete="RESTRICT"), nullable=False
    )
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dim_business_unit.business_unit_id", ondelete="SET NULL"),
        nullable=True,
    )
    division_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_division.division_id", ondelete="SET NULL"), nullable=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_customer.customer_id", ondelete="RESTRICT"), nullable=False
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("variance_detection_rule.rule_id", ondelete="RESTRICT"),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    baseline_amount: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    actual_amount: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    delta: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'USD'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RevenueVarianceExplanation(Base):
    """Append-only explanation rows for a variance case (Story 7.3)."""

    __tablename__ = "revenue_variance_explanation"
    __table_args__ = (
        CheckConstraint(
            "movement_direction IS NULL OR movement_direction IN ('up', 'down', 'flat')",
            name="ck_variance_explanation_movement",
        ),
        Index("idx_variance_explanation_case", "case_id"),
    )

    explanation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("revenue_variance_case.case_id", ondelete="CASCADE"),
        nullable=False,
    )
    explained_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    explanation_text: Mapped[str] = mapped_column(Text, nullable=False)
    movement_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class WorkbookTemplateVersion(Base):
    """Published Excel template registry (platform-wide when tenant_id is null)."""

    __tablename__ = "workbook_template_version"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "template_key",
            "version_label",
            name="uq_workbook_template_version_key",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_workbook_template_tenant", "tenant_id"),
    )

    template_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=True
    )
    template_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    column_map: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class NotificationOutbox(Base):
    """Queued email / notification jobs with opaque token reference (D6)."""

    __tablename__ = "notification_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'cancelled')",
            name="ck_notification_outbox_status",
        ),
        Index("idx_notification_outbox_tenant_status", "tenant_id", "status"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    token_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'pending'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
