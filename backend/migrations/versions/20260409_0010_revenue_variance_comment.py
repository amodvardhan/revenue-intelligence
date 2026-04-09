"""Revenue variance narrative comments (MoM / YoY context) per customer-month matrix scope."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260409_0010"
down_revision: Union[str, None] = "20260409_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE revenue_variance_comment (
    variance_comment_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    org_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    revenue_month DATE NOT NULL,
    business_unit_id UUID,
    division_id UUID,
    comment_text TEXT NOT NULL,
    updated_by_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (variance_comment_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (org_id) REFERENCES dim_organization (org_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES dim_customer (customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (business_unit_id) REFERENCES dim_business_unit (business_unit_id) ON DELETE RESTRICT,
    FOREIGN KEY (division_id) REFERENCES dim_division (division_id) ON DELETE RESTRICT,
    FOREIGN KEY (updated_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL,
    CONSTRAINT uq_revenue_variance_comment_scope UNIQUE NULLS NOT DISTINCT (
        tenant_id, org_id, customer_id, revenue_month, business_unit_id, division_id
    )
);
"""
    )
    op.execute(
        "CREATE INDEX idx_revenue_variance_comment_org_customer "
        "ON revenue_variance_comment (tenant_id, org_id, customer_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS revenue_variance_comment;")
