"""Manual matrix cell overrides and delivery manager — customer assignments (history-aware)."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260408_0008"
down_revision: Union[str, None] = "20260408_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE revenue_manual_cell (
    manual_cell_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    org_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    revenue_month DATE NOT NULL,
    business_unit_id UUID,
    division_id UUID,
    amount NUMERIC(18, 4) NOT NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'USD',
    updated_by_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (manual_cell_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES dim_customer (customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (business_unit_id) REFERENCES dim_business_unit (business_unit_id) ON DELETE RESTRICT,
    FOREIGN KEY (division_id) REFERENCES dim_division (division_id) ON DELETE RESTRICT,
    FOREIGN KEY (updated_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL
);
"""
    )
    op.execute(
        """
CREATE UNIQUE INDEX uq_revenue_manual_cell_scope ON revenue_manual_cell (
    tenant_id,
    org_id,
    customer_id,
    revenue_month,
    COALESCE(business_unit_id::text, ''),
    COALESCE(division_id::text, '')
);
"""
    )
    op.execute("CREATE INDEX idx_revenue_manual_cell_org ON revenue_manual_cell (tenant_id, org_id);")
    op.execute("ALTER TABLE revenue_manual_cell ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY revenue_manual_cell_tenant_isolation ON revenue_manual_cell
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE customer_delivery_manager_assignment (
    assignment_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    org_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    delivery_manager_user_id UUID NOT NULL,
    valid_from DATE NOT NULL DEFAULT (CURRENT_DATE),
    valid_to DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (assignment_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES dim_customer (customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (delivery_manager_user_id) REFERENCES users (user_id) ON DELETE RESTRICT,
    CONSTRAINT ck_dm_assignment_dates CHECK (valid_to IS NULL OR valid_to >= valid_from)
);
"""
    )
    op.execute(
        """
CREATE UNIQUE INDEX uq_dm_one_current_per_customer
ON customer_delivery_manager_assignment (tenant_id, customer_id)
WHERE valid_to IS NULL;
"""
    )
    op.execute(
        "CREATE INDEX idx_dm_assignment_org_customer ON customer_delivery_manager_assignment "
        "(tenant_id, org_id, customer_id);"
    )
    op.execute("ALTER TABLE customer_delivery_manager_assignment ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY customer_dm_assignment_tenant_isolation ON customer_delivery_manager_assignment
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS customer_delivery_manager_assignment;")
    op.execute("DROP TABLE IF EXISTS revenue_manual_cell;")
