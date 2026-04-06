"""Phase 2: BU access, analytics metadata, materialized views, RLS tightening.

Revision ID: 20260403_0002
Revises: 20260403_0001
Create Date: 2026-04-03

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260403_0002"
down_revision: Union[str, None] = "20260403_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE user_business_unit_access (
    user_id UUID NOT NULL,
    business_unit_id UUID NOT NULL,
    PRIMARY KEY (user_id, business_unit_id),
    FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY(business_unit_id) REFERENCES dim_business_unit (business_unit_id) ON DELETE CASCADE
);
"""
    )
    op.execute("CREATE INDEX idx_user_bu_access_user ON user_business_unit_access (user_id);")

    op.execute(
        """
CREATE TABLE analytics_refresh_metadata (
    metadata_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    structure_name VARCHAR(100) NOT NULL,
    last_refresh_started_at TIMESTAMP WITH TIME ZONE,
    last_refresh_completed_at TIMESTAMP WITH TIME ZONE,
    last_completed_batch_id UUID,
    last_error TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (metadata_id),
    CONSTRAINT uq_analytics_refresh_tenant_structure UNIQUE (tenant_id, structure_name),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(last_completed_batch_id) REFERENCES ingestion_batch (batch_id)
);
"""
    )
    op.execute("CREATE INDEX idx_analytics_refresh_tenant ON analytics_refresh_metadata (tenant_id);")

    op.execute(
        """
CREATE MATERIALIZED VIEW mv_revenue_monthly_by_org AS
SELECT
    fr.tenant_id,
    fr.org_id,
    (date_trunc('month', fr.revenue_date::timestamp AT TIME ZONE 'UTC'))::date AS month_start,
    SUM(fr.amount) AS total_amount
FROM fact_revenue fr
WHERE fr.is_deleted = false
GROUP BY fr.tenant_id, fr.org_id, date_trunc('month', fr.revenue_date::timestamp AT TIME ZONE 'UTC');
"""
    )
    op.execute(
        """
CREATE UNIQUE INDEX uq_mv_revenue_monthly_org ON mv_revenue_monthly_by_org (tenant_id, org_id, month_start);
"""
    )

    op.execute(
        """
CREATE MATERIALIZED VIEW mv_revenue_monthly_by_bu AS
SELECT
    fr.tenant_id,
    fr.org_id,
    fr.business_unit_id,
    (date_trunc('month', fr.revenue_date::timestamp AT TIME ZONE 'UTC'))::date AS month_start,
    SUM(fr.amount) AS total_amount
FROM fact_revenue fr
WHERE fr.is_deleted = false AND fr.business_unit_id IS NOT NULL
GROUP BY fr.tenant_id, fr.org_id, fr.business_unit_id, date_trunc('month', fr.revenue_date::timestamp AT TIME ZONE 'UTC');
"""
    )
    op.execute(
        """
CREATE UNIQUE INDEX uq_mv_revenue_monthly_bu ON mv_revenue_monthly_by_bu (tenant_id, business_unit_id, month_start);
"""
    )

    op.execute(
        """
CREATE MATERIALIZED VIEW mv_revenue_monthly_by_division AS
SELECT
    fr.tenant_id,
    fr.org_id,
    fr.business_unit_id,
    fr.division_id,
    (date_trunc('month', fr.revenue_date::timestamp AT TIME ZONE 'UTC'))::date AS month_start,
    SUM(fr.amount) AS total_amount
FROM fact_revenue fr
WHERE fr.is_deleted = false AND fr.division_id IS NOT NULL
GROUP BY fr.tenant_id, fr.org_id, fr.business_unit_id, fr.division_id, date_trunc('month', fr.revenue_date::timestamp AT TIME ZONE 'UTC');
"""
    )
    op.execute(
        """
CREATE UNIQUE INDEX uq_mv_revenue_monthly_division
ON mv_revenue_monthly_by_division (tenant_id, division_id, month_start);
"""
    )

    op.execute("ALTER TABLE analytics_refresh_metadata ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY analytics_refresh_metadata_tenant_isolation ON analytics_refresh_metadata
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute("DROP POLICY IF EXISTS fact_revenue_tenant_isolation ON fact_revenue;")

    op.execute(
        """
CREATE POLICY fact_revenue_select ON fact_revenue FOR SELECT USING (
  tenant_id = current_setting('app.tenant_id', true)::uuid
  AND org_id IN (SELECT uor.org_id FROM user_org_role uor WHERE uor.user_id = current_setting('app.user_id', true)::uuid)
  AND (
    NOT EXISTS (SELECT 1 FROM user_business_unit_access uba WHERE uba.user_id = current_setting('app.user_id', true)::uuid)
    OR (
      business_unit_id IS NOT NULL
      AND business_unit_id IN (
        SELECT uba.business_unit_id FROM user_business_unit_access uba
        WHERE uba.user_id = current_setting('app.user_id', true)::uuid
      )
    )
  )
);
"""
    )

    op.execute(
        """
CREATE POLICY fact_revenue_insert ON fact_revenue FOR INSERT WITH CHECK (
  tenant_id = current_setting('app.tenant_id', true)::uuid
  AND org_id IN (SELECT uor.org_id FROM user_org_role uor WHERE uor.user_id = current_setting('app.user_id', true)::uuid)
);
"""
    )

    op.execute(
        """
CREATE POLICY fact_revenue_update ON fact_revenue FOR UPDATE USING (
  tenant_id = current_setting('app.tenant_id', true)::uuid
) WITH CHECK (
  tenant_id = current_setting('app.tenant_id', true)::uuid
);
"""
    )

    op.execute(
        """
CREATE POLICY fact_revenue_delete ON fact_revenue FOR DELETE USING (
  tenant_id = current_setting('app.tenant_id', true)::uuid
);
"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS fact_revenue_delete ON fact_revenue;")
    op.execute("DROP POLICY IF EXISTS fact_revenue_update ON fact_revenue;")
    op.execute("DROP POLICY IF EXISTS fact_revenue_insert ON fact_revenue;")
    op.execute("DROP POLICY IF EXISTS fact_revenue_select ON fact_revenue;")

    op.execute(
        """
CREATE POLICY fact_revenue_tenant_isolation ON fact_revenue
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute("DROP POLICY IF EXISTS analytics_refresh_metadata_tenant_isolation ON analytics_refresh_metadata;")
    op.execute("ALTER TABLE analytics_refresh_metadata DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_revenue_monthly_by_division;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_revenue_monthly_by_bu;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_revenue_monthly_by_org;")

    op.execute("DROP TABLE IF EXISTS analytics_refresh_metadata;")
    op.execute("DROP TABLE IF EXISTS user_business_unit_access;")
