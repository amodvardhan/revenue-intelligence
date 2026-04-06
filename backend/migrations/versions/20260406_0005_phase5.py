"""Phase 5 — FX, forecast, cost, segments; optional fact_revenue reporting columns."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260406_0005"
down_revision: Union[str, None] = "20260406_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE fx_rate (
    fx_rate_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    base_currency_code CHAR(3) NOT NULL,
    quote_currency_code CHAR(3) NOT NULL,
    effective_date DATE NOT NULL,
    rate NUMERIC(18, 10) NOT NULL,
    rate_source VARCHAR(50) NOT NULL,
    notes TEXT,
    ingestion_batch_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (fx_rate_id),
    CONSTRAINT uq_fx_rate_tenant_pair_date UNIQUE (tenant_id, base_currency_code, quote_currency_code, effective_date),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (ingestion_batch_id) REFERENCES ingestion_batch (batch_id) ON DELETE SET NULL
);
"""
    )
    op.execute(
        "CREATE INDEX idx_fx_rate_tenant_effective ON fx_rate (tenant_id, effective_date DESC);"
    )
    op.execute("ALTER TABLE fx_rate ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY fx_rate_tenant_isolation ON fx_rate
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute("ALTER TABLE fact_revenue ADD COLUMN IF NOT EXISTS amount_reporting_currency NUMERIC(18,4);")
    op.execute(
        """
ALTER TABLE fact_revenue ADD COLUMN IF NOT EXISTS fx_rate_id UUID
  REFERENCES fx_rate(fx_rate_id) ON DELETE SET NULL;
"""
    )
    op.execute(
        """
CREATE INDEX IF NOT EXISTS idx_fact_revenue_fx_rate ON fact_revenue(fx_rate_id)
  WHERE fx_rate_id IS NOT NULL;
"""
    )

    op.execute(
        """
CREATE TABLE forecast_series (
    forecast_series_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    label VARCHAR(200) NOT NULL,
    scenario VARCHAR(50),
    source_mode VARCHAR(50) NOT NULL,
    methodology JSONB,
    effective_from DATE,
    effective_to DATE,
    superseded_by_series_id UUID,
    created_by_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (forecast_series_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by_user_id) REFERENCES users (user_id),
    FOREIGN KEY (superseded_by_series_id) REFERENCES forecast_series (forecast_series_id) ON DELETE SET NULL
);
"""
    )
    op.execute(
        "CREATE INDEX idx_forecast_series_tenant_created ON forecast_series (tenant_id, created_at DESC);"
    )
    op.execute("ALTER TABLE forecast_series ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY forecast_series_tenant_isolation ON forecast_series
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE fact_forecast (
    forecast_fact_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    forecast_series_id UUID NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    currency_code CHAR(3) NOT NULL,
    org_id UUID NOT NULL,
    business_unit_id UUID,
    division_id UUID,
    customer_id UUID,
    external_id VARCHAR(255) NOT NULL,
    batch_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (forecast_fact_id),
    CONSTRAINT uq_fact_forecast_series_external UNIQUE (forecast_series_id, external_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (forecast_series_id) REFERENCES forecast_series (forecast_series_id) ON DELETE CASCADE,
    FOREIGN KEY (org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT,
    FOREIGN KEY (business_unit_id) REFERENCES dim_business_unit (business_unit_id) ON DELETE RESTRICT,
    FOREIGN KEY (division_id) REFERENCES dim_division (division_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES dim_customer (customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (batch_id) REFERENCES ingestion_batch (batch_id) ON DELETE RESTRICT
);
"""
    )
    op.execute(
        "CREATE INDEX idx_fact_forecast_series_period ON fact_forecast (forecast_series_id, period_start);"
    )
    op.execute("CREATE INDEX idx_fact_forecast_tenant ON fact_forecast (tenant_id, period_start);")
    op.execute("ALTER TABLE fact_forecast ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY fact_forecast_tenant_isolation ON fact_forecast
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE fact_cost (
    cost_fact_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    currency_code CHAR(3) NOT NULL,
    cost_date DATE NOT NULL,
    cost_category VARCHAR(100) NOT NULL,
    org_id UUID NOT NULL,
    business_unit_id UUID,
    division_id UUID,
    customer_id UUID,
    source_system VARCHAR(100) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    batch_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (cost_fact_id),
    CONSTRAINT uq_fact_cost_tenant_source_external UNIQUE (tenant_id, source_system, external_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT,
    FOREIGN KEY (business_unit_id) REFERENCES dim_business_unit (business_unit_id) ON DELETE RESTRICT,
    FOREIGN KEY (division_id) REFERENCES dim_division (division_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES dim_customer (customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (batch_id) REFERENCES ingestion_batch (batch_id) ON DELETE RESTRICT
);
"""
    )
    op.execute("CREATE INDEX idx_fact_cost_tenant_date ON fact_cost (tenant_id, cost_date);")
    op.execute("CREATE INDEX idx_fact_cost_org ON fact_cost (org_id, cost_date);")
    op.execute("ALTER TABLE fact_cost ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY fact_cost_tenant_isolation ON fact_cost
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE cost_allocation_rule (
    rule_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    version_label VARCHAR(100) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    basis VARCHAR(50) NOT NULL,
    rule_definition JSONB NOT NULL,
    created_by_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    superseded_by_rule_id UUID,
    PRIMARY KEY (rule_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by_user_id) REFERENCES users (user_id),
    FOREIGN KEY (superseded_by_rule_id) REFERENCES cost_allocation_rule (rule_id) ON DELETE SET NULL
);
"""
    )
    op.execute(
        "CREATE INDEX idx_cost_alloc_rule_tenant_effective ON cost_allocation_rule (tenant_id, effective_from);"
    )
    op.execute("ALTER TABLE cost_allocation_rule ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY cost_allocation_rule_tenant_isolation ON cost_allocation_rule
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE segment_definition (
    segment_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    name VARCHAR(200) NOT NULL,
    rule_definition JSONB NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    owner_org_id UUID,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_by_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (segment_id),
    CONSTRAINT uq_segment_definition_tenant_name UNIQUE (tenant_id, name),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (owner_org_id) REFERENCES dim_organization (org_id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_user_id) REFERENCES users (user_id)
);
"""
    )
    op.execute("ALTER TABLE segment_definition ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY segment_definition_tenant_isolation ON segment_definition
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE segment_membership (
    membership_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    segment_id UUID NOT NULL,
    segment_version INTEGER NOT NULL,
    customer_id UUID NOT NULL,
    period_start DATE,
    period_end DATE,
    as_of_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (membership_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (segment_id) REFERENCES segment_definition (segment_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES dim_customer (customer_id) ON DELETE CASCADE
);
"""
    )
    op.execute(
        "CREATE INDEX idx_segment_membership_segment ON segment_membership (segment_id, segment_version);"
    )
    op.execute("CREATE INDEX idx_segment_membership_customer ON segment_membership (customer_id);")
    op.execute("ALTER TABLE segment_membership ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY segment_membership_tenant_isolation ON segment_membership
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE UNIQUE INDEX uq_segment_membership_period
  ON segment_membership (segment_id, segment_version, customer_id, period_start, period_end)
  WHERE period_start IS NOT NULL AND period_end IS NOT NULL;
"""
    )
    op.execute(
        """
CREATE UNIQUE INDEX uq_segment_membership_as_of
  ON segment_membership (segment_id, segment_version, customer_id, as_of_date)
  WHERE as_of_date IS NOT NULL;
"""
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_segment_membership_as_of;")
    op.execute("DROP INDEX IF EXISTS uq_segment_membership_period;")
    op.execute("DROP TABLE IF EXISTS segment_membership;")
    op.execute("DROP TABLE IF EXISTS segment_definition;")
    op.execute("DROP TABLE IF EXISTS cost_allocation_rule;")
    op.execute("DROP TABLE IF EXISTS fact_cost;")
    op.execute("DROP TABLE IF EXISTS fact_forecast;")
    op.execute("DROP TABLE IF EXISTS forecast_series;")
    op.execute("DROP INDEX IF EXISTS idx_fact_revenue_fx_rate;")
    op.execute("ALTER TABLE fact_revenue DROP COLUMN IF EXISTS fx_rate_id;")
    op.execute("ALTER TABLE fact_revenue DROP COLUMN IF EXISTS amount_reporting_currency;")
    op.execute("DROP TABLE IF EXISTS fx_rate;")
