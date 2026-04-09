"""Phase 7 — customer common name, variance cases, workbook template registry, notification outbox."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260408_0007"
down_revision: Union[str, None] = "20260406_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
ALTER TABLE dim_customer
  ADD COLUMN IF NOT EXISTS customer_name_common VARCHAR(255);
"""
    )
    op.execute(
        """
UPDATE dim_customer SET customer_name_common = customer_name WHERE customer_name_common IS NULL;
"""
    )

    op.execute(
        """
CREATE TABLE variance_detection_rule (
    rule_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    comparison_type VARCHAR(50) NOT NULL,
    min_abs_delta NUMERIC(18, 4),
    min_pct NUMERIC(18, 6),
    org_id UUID,
    business_unit_id UUID,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (rule_id),
    CONSTRAINT ck_variance_rule_comparison_type CHECK (
        comparison_type IN ('mom', 'yoy', 'vs_goal')
    ),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (org_id) REFERENCES dim_organization (org_id) ON DELETE SET NULL,
    FOREIGN KEY (business_unit_id) REFERENCES dim_business_unit (business_unit_id) ON DELETE SET NULL
);
"""
    )
    op.execute("CREATE INDEX idx_variance_rule_tenant ON variance_detection_rule (tenant_id);")
    op.execute("ALTER TABLE variance_detection_rule ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY variance_detection_rule_tenant_isolation ON variance_detection_rule
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE revenue_variance_case (
    case_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    org_id UUID NOT NULL,
    business_unit_id UUID,
    division_id UUID,
    customer_id UUID NOT NULL,
    period_month DATE NOT NULL,
    rule_id UUID NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    baseline_amount NUMERIC(18, 4),
    actual_amount NUMERIC(18, 4),
    delta NUMERIC(18, 4),
    currency_code CHAR(3) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (case_id),
    CONSTRAINT ck_variance_case_severity CHECK (severity IN ('info', 'warning', 'critical')),
    CONSTRAINT ck_variance_case_status CHECK (status IN ('open', 'explained', 'dismissed')),
    CONSTRAINT uq_variance_case_natural_key UNIQUE NULLS NOT DISTINCT (
        tenant_id, rule_id, customer_id, period_month, division_id
    ),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT,
    FOREIGN KEY (business_unit_id) REFERENCES dim_business_unit (business_unit_id) ON DELETE SET NULL,
    FOREIGN KEY (division_id) REFERENCES dim_division (division_id) ON DELETE SET NULL,
    FOREIGN KEY (customer_id) REFERENCES dim_customer (customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (rule_id) REFERENCES variance_detection_rule (rule_id) ON DELETE RESTRICT
);
"""
    )
    op.execute(
        """
CREATE INDEX idx_variance_case_tenant_status_created
ON revenue_variance_case (tenant_id, status, created_at);
"""
    )
    op.execute(
        """
CREATE INDEX idx_variance_case_tenant_customer_period
ON revenue_variance_case (tenant_id, customer_id, period_month);
"""
    )
    op.execute("ALTER TABLE revenue_variance_case ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY revenue_variance_case_tenant_isolation ON revenue_variance_case
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE revenue_variance_explanation (
    explanation_id UUID DEFAULT gen_random_uuid() NOT NULL,
    case_id UUID NOT NULL,
    explained_by_user_id UUID NOT NULL,
    explanation_text TEXT NOT NULL,
    movement_direction VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (explanation_id),
    CONSTRAINT ck_variance_explanation_movement CHECK (
        movement_direction IS NULL OR movement_direction IN ('up', 'down', 'flat')
    ),
    FOREIGN KEY (case_id) REFERENCES revenue_variance_case (case_id) ON DELETE CASCADE,
    FOREIGN KEY (explained_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT
);
"""
    )
    op.execute(
        "CREATE INDEX idx_variance_explanation_case ON revenue_variance_explanation (case_id);"
    )
    op.execute("ALTER TABLE revenue_variance_explanation ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY revenue_variance_explanation_tenant_isolation ON revenue_variance_explanation
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM revenue_variance_case c
      WHERE c.case_id = revenue_variance_explanation.case_id
        AND c.tenant_id = current_setting('app.tenant_id', true)::uuid
    )
  );
"""
    )

    op.execute(
        """
CREATE TABLE workbook_template_version (
    template_version_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID,
    template_key VARCHAR(100) NOT NULL,
    version_label VARCHAR(50) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    primary_sheet_name VARCHAR(255) NOT NULL,
    column_map JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (template_version_id),
    CONSTRAINT uq_workbook_template_version_key UNIQUE NULLS NOT DISTINCT (
        tenant_id, template_key, version_label
    ),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE
);
"""
    )
    op.execute(
        "CREATE INDEX idx_workbook_template_tenant ON workbook_template_version (tenant_id);"
    )
    op.execute("ALTER TABLE workbook_template_version ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY workbook_template_version_tenant_isolation ON workbook_template_version
  FOR ALL
  USING (
    tenant_id IS NULL
    OR tenant_id = current_setting('app.tenant_id', true)::uuid
  );
"""
    )

    op.execute(
        """
CREATE TABLE notification_outbox (
    notification_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    recipient_user_id UUID NOT NULL,
    payload JSONB NOT NULL,
    token_reference VARCHAR(128) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (notification_id),
    CONSTRAINT ck_notification_outbox_status CHECK (
        status IN ('pending', 'sent', 'failed', 'cancelled')
    ),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (recipient_user_id) REFERENCES users (user_id) ON DELETE CASCADE
);
"""
    )
    op.execute(
        """
CREATE INDEX idx_notification_outbox_tenant_status
ON notification_outbox (tenant_id, status);
"""
    )
    op.execute("ALTER TABLE notification_outbox ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY notification_outbox_tenant_isolation ON notification_outbox
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notification_outbox CASCADE;")
    op.execute("DROP TABLE IF EXISTS workbook_template_version CASCADE;")
    op.execute("DROP TABLE IF EXISTS revenue_variance_explanation CASCADE;")
    op.execute("DROP TABLE IF EXISTS revenue_variance_case CASCADE;")
    op.execute("DROP TABLE IF EXISTS variance_detection_rule CASCADE;")
    op.execute("ALTER TABLE dim_customer DROP COLUMN IF EXISTS customer_name_common;")
