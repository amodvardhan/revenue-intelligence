"""dim_project — optional customer-scoped delivery / engagement record per org."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260409_0009"
down_revision: Union[str, None] = "20260408_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE dim_project (
    project_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    org_id UUID NOT NULL,
    customer_id UUID,
    project_name VARCHAR(255) NOT NULL,
    project_code VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (project_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES dim_customer (customer_id) ON DELETE SET NULL
);
"""
    )
    op.execute("CREATE INDEX idx_dim_project_tenant_org ON dim_project (tenant_id, org_id);")
    op.execute(
        "CREATE INDEX idx_dim_project_customer ON dim_project (tenant_id, customer_id) "
        "WHERE customer_id IS NOT NULL;"
    )
    op.execute("ALTER TABLE dim_project ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY dim_project_tenant_isolation ON dim_project
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dim_project;")
