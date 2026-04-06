"""Initial schema: dimensions, facts, ingestion, audit, RLS (Phase 1).

Revision ID: 20260403_0001
Revises:
Create Date: 2026-04-03

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260403_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE tenants (
    tenant_id UUID DEFAULT gen_random_uuid() NOT NULL,
    name VARCHAR(255) NOT NULL,
    default_currency_code VARCHAR(3) DEFAULT 'USD' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (tenant_id)
);
"""
    )
    op.execute(
        """
CREATE TABLE dim_organization (
    org_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    org_name VARCHAR(255) NOT NULL,
    parent_org_id UUID,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (org_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(parent_org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT
);
"""
    )
    op.execute(
        """
CREATE TABLE dim_revenue_type (
    revenue_type_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    revenue_type_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (revenue_type_id),
    CONSTRAINT uq_dim_revenue_type_tenant_name UNIQUE (tenant_id, revenue_type_name),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT
);
"""
    )
    op.execute(
        """
CREATE TABLE users (
    user_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash VARCHAR(255),
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (user_id),
    CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT
);
"""
    )
    op.execute(
        """
CREATE TABLE audit_event (
    event_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (event_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(user_id) REFERENCES users (user_id)
);
"""
    )
    op.execute(
        """
CREATE TABLE dim_business_unit (
    business_unit_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    business_unit_name VARCHAR(255) NOT NULL,
    org_id UUID NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (business_unit_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT
);
"""
    )
    op.execute(
        """
CREATE TABLE dim_customer (
    customer_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    customer_code VARCHAR(100),
    org_id UUID,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (customer_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(org_id) REFERENCES dim_organization (org_id) ON DELETE SET NULL
);
"""
    )
    op.execute(
        """
CREATE TABLE ingestion_batch (
    batch_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    source_system VARCHAR(100) NOT NULL,
    filename VARCHAR(500),
    storage_key VARCHAR(1024),
    file_sha256 VARCHAR(64),
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    total_rows INTEGER,
    loaded_rows INTEGER DEFAULT 0 NOT NULL,
    error_rows INTEGER DEFAULT 0 NOT NULL,
    error_log JSONB,
    period_start DATE,
    period_end DATE,
    scope_org_id UUID,
    replace_of_batch_id UUID,
    initiated_by UUID,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (batch_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(scope_org_id) REFERENCES dim_organization (org_id),
    FOREIGN KEY(replace_of_batch_id) REFERENCES ingestion_batch (batch_id),
    FOREIGN KEY(initiated_by) REFERENCES users (user_id)
);
"""
    )
    op.execute(
        """
CREATE TABLE query_audit_log (
    log_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    user_id UUID,
    natural_query TEXT NOT NULL,
    resolved_plan JSONB,
    execution_ms INTEGER,
    row_count INTEGER,
    status VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (log_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(user_id) REFERENCES users (user_id)
);
"""
    )
    op.execute(
        """
CREATE TABLE user_org_role (
    user_id UUID NOT NULL,
    org_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (user_id, org_id),
    CONSTRAINT ck_user_org_role_role CHECK (role IN ('admin', 'cxo', 'bu_head', 'finance', 'viewer', 'it_admin')),
    FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY(org_id) REFERENCES dim_organization (org_id) ON DELETE CASCADE
);
"""
    )
    op.execute(
        """
CREATE TABLE dim_division (
    division_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    division_name VARCHAR(255) NOT NULL,
    business_unit_id UUID NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (division_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(business_unit_id) REFERENCES dim_business_unit (business_unit_id) ON DELETE RESTRICT
);
"""
    )
    op.execute(
        """
CREATE TABLE fact_revenue (
    revenue_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    currency_code VARCHAR(3) DEFAULT 'USD' NOT NULL,
    revenue_date DATE NOT NULL,
    org_id UUID NOT NULL,
    business_unit_id UUID,
    division_id UUID,
    customer_id UUID,
    revenue_type_id UUID,
    source_system VARCHAR(100) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    batch_id UUID,
    is_deleted BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (revenue_id),
    CONSTRAINT uq_fact_revenue_source_external UNIQUE (source_system, external_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY(org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT,
    FOREIGN KEY(business_unit_id) REFERENCES dim_business_unit (business_unit_id) ON DELETE RESTRICT,
    FOREIGN KEY(division_id) REFERENCES dim_division (division_id) ON DELETE RESTRICT,
    FOREIGN KEY(customer_id) REFERENCES dim_customer (customer_id) ON DELETE RESTRICT,
    FOREIGN KEY(revenue_type_id) REFERENCES dim_revenue_type (revenue_type_id) ON DELETE RESTRICT,
    FOREIGN KEY(batch_id) REFERENCES ingestion_batch (batch_id) ON DELETE RESTRICT
);
"""
    )

    op.execute("CREATE INDEX idx_dim_org_tenant ON dim_organization (tenant_id);")
    op.execute("CREATE INDEX idx_dim_org_parent ON dim_organization (parent_org_id);")
    op.execute("CREATE INDEX idx_users_tenant ON users (tenant_id);")
    op.execute(
        "CREATE INDEX idx_audit_event_tenant_created ON audit_event (tenant_id, created_at);"
    )
    op.execute(
        "CREATE INDEX idx_dim_bu_tenant_org ON dim_business_unit (tenant_id, org_id);"
    )
    op.execute(
        """
CREATE UNIQUE INDEX uq_dim_customer_tenant_code
ON dim_customer (tenant_id, customer_code)
WHERE customer_code IS NOT NULL;
"""
    )
    op.execute(
        "CREATE INDEX idx_ingestion_batch_started ON ingestion_batch (started_at DESC);"
    )
    op.execute(
        "CREATE INDEX idx_ingestion_batch_tenant_status ON ingestion_batch (tenant_id, status);"
    )
    op.execute(
        "CREATE INDEX idx_query_audit_tenant_created ON query_audit_log (tenant_id, created_at);"
    )
    op.execute("CREATE INDEX idx_user_org_role_org ON user_org_role (org_id);")
    op.execute("CREATE INDEX idx_dim_division_bu ON dim_division (business_unit_id);")
    op.execute("CREATE INDEX idx_fact_revenue_date ON fact_revenue (revenue_date);")
    op.execute(
        "CREATE INDEX idx_fact_revenue_source ON fact_revenue (source_system, external_id);"
    )
    op.execute(
        """
CREATE INDEX idx_fact_revenue_bu ON fact_revenue (business_unit_id, revenue_date)
WHERE business_unit_id IS NOT NULL;
"""
    )
    op.execute(
        """
CREATE INDEX idx_fact_revenue_org ON fact_revenue (tenant_id, org_id, revenue_date);
"""
    )
    op.execute(
        """
CREATE INDEX idx_fact_revenue_division ON fact_revenue (division_id, revenue_date)
WHERE division_id IS NOT NULL;
"""
    )
    op.execute("CREATE INDEX idx_fact_revenue_batch ON fact_revenue (batch_id);")

    op.execute("ALTER TABLE fact_revenue ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY fact_revenue_tenant_isolation ON fact_revenue
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )
    op.execute("ALTER TABLE ingestion_batch ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY ingestion_batch_tenant_isolation ON ingestion_batch
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )
    op.execute("ALTER TABLE query_audit_log ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY query_audit_log_tenant_isolation ON query_audit_log
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )
    op.execute("ALTER TABLE audit_event ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY audit_event_tenant_isolation ON audit_event
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_event_tenant_isolation ON audit_event;")
    op.execute("ALTER TABLE audit_event DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS query_audit_log_tenant_isolation ON query_audit_log;")
    op.execute("ALTER TABLE query_audit_log DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS ingestion_batch_tenant_isolation ON ingestion_batch;")
    op.execute("ALTER TABLE ingestion_batch DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS fact_revenue_tenant_isolation ON fact_revenue;")
    op.execute("ALTER TABLE fact_revenue DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP TABLE IF EXISTS fact_revenue CASCADE;")
    op.execute("DROP TABLE IF EXISTS dim_division CASCADE;")
    op.execute("DROP TABLE IF EXISTS user_org_role CASCADE;")
    op.execute("DROP TABLE IF EXISTS query_audit_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS ingestion_batch CASCADE;")
    op.execute("DROP TABLE IF EXISTS dim_customer CASCADE;")
    op.execute("DROP TABLE IF EXISTS dim_business_unit CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_event CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TABLE IF EXISTS dim_revenue_type CASCADE;")
    op.execute("DROP TABLE IF EXISTS dim_organization CASCADE;")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE;")
