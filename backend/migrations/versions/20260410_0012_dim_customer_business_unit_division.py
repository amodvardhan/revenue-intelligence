"""dim_customer: optional business_unit_id and division_id for commercial hierarchy."""

from __future__ import annotations

from alembic import op

revision = "20260410_0012"
down_revision = "20260410_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE dim_customer
        ADD COLUMN IF NOT EXISTS business_unit_id UUID
            REFERENCES dim_business_unit (business_unit_id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE dim_customer
        ADD COLUMN IF NOT EXISTS division_id UUID
            REFERENCES dim_division (division_id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE dim_customer
        ADD CONSTRAINT ck_dim_customer_division_requires_bu
        CHECK (division_id IS NULL OR business_unit_id IS NOT NULL);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dim_customer_org_bu
        ON dim_customer (tenant_id, org_id, business_unit_id)
        WHERE business_unit_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trf_dim_customer_bu_div_alignment()
        RETURNS TRIGGER AS $$
        BEGIN
          IF NEW.business_unit_id IS NOT NULL THEN
            IF NOT EXISTS (
              SELECT 1 FROM dim_business_unit bu
              WHERE bu.business_unit_id = NEW.business_unit_id
                AND bu.tenant_id = NEW.tenant_id
                AND (NEW.org_id IS NULL OR bu.org_id = NEW.org_id)
            ) THEN
              RAISE EXCEPTION 'dim_customer.business_unit_id must belong to the same tenant and organization as the customer';
            END IF;
          END IF;
          IF NEW.division_id IS NOT NULL THEN
            IF NEW.business_unit_id IS NULL THEN
              RAISE EXCEPTION 'dim_customer.division_id requires business_unit_id';
            END IF;
            IF NOT EXISTS (
              SELECT 1 FROM dim_division d
              WHERE d.division_id = NEW.division_id
                AND d.business_unit_id = NEW.business_unit_id
                AND d.tenant_id = NEW.tenant_id
            ) THEN
              RAISE EXCEPTION 'dim_customer.division_id must belong to the given business_unit_id';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_dim_customer_bu_div_alignment ON dim_customer;")
    op.execute(
        """
        CREATE TRIGGER trg_dim_customer_bu_div_alignment
        BEFORE INSERT OR UPDATE OF business_unit_id, division_id, org_id, tenant_id
        ON dim_customer
        FOR EACH ROW
        EXECUTE FUNCTION trf_dim_customer_bu_div_alignment();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_dim_customer_bu_div_alignment ON dim_customer;")
    op.execute("DROP FUNCTION IF EXISTS trf_dim_customer_bu_div_alignment();")
    op.execute("ALTER TABLE dim_customer DROP CONSTRAINT IF EXISTS ck_dim_customer_division_requires_bu;")
    op.execute("DROP INDEX IF EXISTS idx_dim_customer_org_bu;")
    op.execute("ALTER TABLE dim_customer DROP COLUMN IF EXISTS division_id;")
    op.execute("ALTER TABLE dim_customer DROP COLUMN IF EXISTS business_unit_id;")
