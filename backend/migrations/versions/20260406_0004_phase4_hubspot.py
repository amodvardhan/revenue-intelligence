"""Phase 4 — HubSpot integration tables, fact_revenue.source_metadata."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260406_0004"
down_revision: Union[str, None] = "20260406_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE fact_revenue ADD COLUMN source_metadata JSONB;")

    op.execute(
        """
CREATE TABLE hubspot_connection (
    connection_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    hubspot_portal_id VARCHAR(64),
    status VARCHAR(50) NOT NULL,
    encrypted_token_bundle TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE,
    scopes_granted TEXT,
    last_token_refresh_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    connected_by_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (connection_id),
    CONSTRAINT uq_hubspot_connection_tenant UNIQUE (tenant_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(connected_by_user_id) REFERENCES users (user_id)
);
"""
    )
    op.execute(
        "CREATE INDEX idx_hubspot_connection_status ON hubspot_connection (tenant_id, status);"
    )
    op.execute("ALTER TABLE hubspot_connection ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY hubspot_connection_tenant_isolation ON hubspot_connection
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE hubspot_sync_cursor (
    cursor_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    object_type VARCHAR(50) NOT NULL,
    cursor_payload JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (cursor_id),
    CONSTRAINT uq_hubspot_sync_cursor_tenant_object UNIQUE (tenant_id, object_type),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT
);
"""
    )
    op.execute("ALTER TABLE hubspot_sync_cursor ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY hubspot_sync_cursor_tenant_isolation ON hubspot_sync_cursor
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE hubspot_id_mapping (
    mapping_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    hubspot_object_type VARCHAR(50) NOT NULL,
    hubspot_object_id VARCHAR(64) NOT NULL,
    customer_id UUID,
    org_id UUID,
    status VARCHAR(50) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (mapping_id),
    CONSTRAINT uq_hubspot_id_mapping_object UNIQUE (tenant_id, hubspot_object_type, hubspot_object_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(customer_id) REFERENCES dim_customer (customer_id) ON DELETE SET NULL,
    FOREIGN KEY(org_id) REFERENCES dim_organization (org_id) ON DELETE SET NULL
);
"""
    )
    op.execute(
        "CREATE INDEX idx_hubspot_mapping_tenant_status ON hubspot_id_mapping (tenant_id, status);"
    )
    op.execute("ALTER TABLE hubspot_id_mapping ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY hubspot_id_mapping_tenant_isolation ON hubspot_id_mapping
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE integration_sync_run (
    sync_run_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    integration_code VARCHAR(50) NOT NULL,
    trigger VARCHAR(50) NOT NULL,
    initiated_by_user_id UUID,
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    rows_fetched INTEGER DEFAULT 0 NOT NULL,
    rows_loaded INTEGER DEFAULT 0 NOT NULL,
    rows_failed INTEGER DEFAULT 0 NOT NULL,
    error_summary TEXT,
    correlation_id UUID,
    stats JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (sync_run_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(initiated_by_user_id) REFERENCES users (user_id)
);
"""
    )
    op.execute(
        """
CREATE INDEX idx_integration_sync_run_tenant_started
ON integration_sync_run (tenant_id, started_at DESC);
"""
    )
    op.execute("ALTER TABLE integration_sync_run ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY integration_sync_run_tenant_isolation ON integration_sync_run
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE revenue_source_conflict (
    conflict_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    reconciliation_key VARCHAR(512) NOT NULL,
    customer_id UUID,
    period_start DATE,
    period_end DATE,
    excel_amount NUMERIC(18, 4),
    hubspot_amount NUMERIC(18, 4),
    excel_fact_id UUID,
    hubspot_fact_id UUID,
    status VARCHAR(50) NOT NULL,
    resolution_notes TEXT,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (conflict_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(customer_id) REFERENCES dim_customer (customer_id),
    FOREIGN KEY(excel_fact_id) REFERENCES fact_revenue (revenue_id),
    FOREIGN KEY(hubspot_fact_id) REFERENCES fact_revenue (revenue_id)
);
"""
    )
    op.execute(
        "CREATE INDEX idx_revenue_conflict_tenant_status ON revenue_source_conflict (tenant_id, status);"
    )
    op.execute(
        "CREATE INDEX idx_revenue_conflict_detected ON revenue_source_conflict (tenant_id, detected_at DESC);"
    )
    op.execute("ALTER TABLE revenue_source_conflict ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY revenue_source_conflict_tenant_isolation ON revenue_source_conflict
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE hubspot_deal_staging (
    staging_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    sync_run_id UUID NOT NULL,
    hubspot_deal_id VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    validation_status VARCHAR(50) NOT NULL,
    error_detail JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (staging_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(sync_run_id) REFERENCES integration_sync_run (sync_run_id) ON DELETE CASCADE
);
"""
    )
    op.execute("CREATE INDEX idx_hubspot_staging_run ON hubspot_deal_staging (sync_run_id);")
    op.execute(
        "CREATE INDEX idx_hubspot_staging_deal ON hubspot_deal_staging (tenant_id, hubspot_deal_id);"
    )
    op.execute("ALTER TABLE hubspot_deal_staging ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY hubspot_deal_staging_tenant_isolation ON hubspot_deal_staging
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS hubspot_deal_staging_tenant_isolation ON hubspot_deal_staging;")
    op.execute("ALTER TABLE hubspot_deal_staging DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TABLE IF EXISTS hubspot_deal_staging CASCADE;")

    op.execute("DROP POLICY IF EXISTS revenue_source_conflict_tenant_isolation ON revenue_source_conflict;")
    op.execute("ALTER TABLE revenue_source_conflict DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TABLE IF EXISTS revenue_source_conflict CASCADE;")

    op.execute("DROP POLICY IF EXISTS integration_sync_run_tenant_isolation ON integration_sync_run;")
    op.execute("ALTER TABLE integration_sync_run DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TABLE IF EXISTS integration_sync_run CASCADE;")

    op.execute("DROP POLICY IF EXISTS hubspot_id_mapping_tenant_isolation ON hubspot_id_mapping;")
    op.execute("ALTER TABLE hubspot_id_mapping DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TABLE IF EXISTS hubspot_id_mapping CASCADE;")

    op.execute("DROP POLICY IF EXISTS hubspot_sync_cursor_tenant_isolation ON hubspot_sync_cursor;")
    op.execute("ALTER TABLE hubspot_sync_cursor DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TABLE IF EXISTS hubspot_sync_cursor CASCADE;")

    op.execute("DROP POLICY IF EXISTS hubspot_connection_tenant_isolation ON hubspot_connection;")
    op.execute("ALTER TABLE hubspot_connection DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TABLE IF EXISTS hubspot_connection CASCADE;")

    op.execute("ALTER TABLE fact_revenue DROP COLUMN IF EXISTS source_metadata;")
