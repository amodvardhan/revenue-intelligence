"""Phase 3 — semantic_layer_version, nl_query_session, query_audit_log extensions."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260406_0003"
down_revision: Union[str, None] = "20260403_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE semantic_layer_version (
    version_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    version_label VARCHAR(100) NOT NULL,
    source_identifier VARCHAR(255),
    content_sha256 CHAR(64),
    effective_from TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (version_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT
);
"""
    )
    op.execute(
        "CREATE INDEX idx_semantic_layer_version_tenant ON semantic_layer_version (tenant_id);"
    )
    op.execute(
        """
CREATE UNIQUE INDEX uq_semantic_layer_one_active_per_tenant
ON semantic_layer_version (tenant_id)
WHERE is_active = TRUE;
"""
    )
    op.execute("ALTER TABLE semantic_layer_version ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY semantic_layer_version_tenant_isolation ON semantic_layer_version
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE nl_query_session (
    nl_session_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    status VARCHAR(50) NOT NULL,
    pending_context JSONB,
    token_hash CHAR(64),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (nl_session_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);
"""
    )
    op.execute(
        "CREATE INDEX idx_nl_query_session_user_created ON nl_query_session (user_id, created_at DESC);"
    )
    op.execute(
        "CREATE INDEX idx_nl_query_session_expires ON nl_query_session (expires_at);"
    )
    op.execute("ALTER TABLE nl_query_session ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY nl_query_session_tenant_isolation ON nl_query_session
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute("ALTER TABLE query_audit_log ADD COLUMN correlation_id UUID;")
    op.execute("ALTER TABLE query_audit_log ADD COLUMN nl_session_id UUID;")
    op.execute("ALTER TABLE query_audit_log ADD COLUMN semantic_version_id UUID;")
    op.execute(
        """
ALTER TABLE query_audit_log
  ADD CONSTRAINT fk_query_audit_nl_session
  FOREIGN KEY (nl_session_id) REFERENCES nl_query_session (nl_session_id) ON DELETE SET NULL;
"""
    )
    op.execute(
        """
ALTER TABLE query_audit_log
  ADD CONSTRAINT fk_query_audit_semantic_version
  FOREIGN KEY (semantic_version_id) REFERENCES semantic_layer_version (version_id) ON DELETE SET NULL;
"""
    )
    op.execute(
        """
CREATE INDEX idx_query_audit_correlation ON query_audit_log (correlation_id)
WHERE correlation_id IS NOT NULL;
"""
    )

    op.execute(
        """
INSERT INTO semantic_layer_version (tenant_id, version_label, source_identifier, content_sha256, is_active)
SELECT tenant_id, '2026.04.1', 'semantic_layer.yaml',
       '0000000000000000000000000000000000000000000000000000000000000000', true
FROM tenants;
"""
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_query_audit_correlation;")
    op.execute("ALTER TABLE query_audit_log DROP CONSTRAINT IF EXISTS fk_query_audit_semantic_version;")
    op.execute("ALTER TABLE query_audit_log DROP CONSTRAINT IF EXISTS fk_query_audit_nl_session;")
    op.execute("ALTER TABLE query_audit_log DROP COLUMN IF EXISTS semantic_version_id;")
    op.execute("ALTER TABLE query_audit_log DROP COLUMN IF EXISTS nl_session_id;")
    op.execute("ALTER TABLE query_audit_log DROP COLUMN IF EXISTS correlation_id;")

    op.execute("DROP POLICY IF EXISTS nl_query_session_tenant_isolation ON nl_query_session;")
    op.execute("ALTER TABLE nl_query_session DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TABLE IF EXISTS nl_query_session CASCADE;")

    op.execute("DROP POLICY IF EXISTS semantic_layer_version_tenant_isolation ON semantic_layer_version;")
    op.execute("ALTER TABLE semantic_layer_version DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TABLE IF EXISTS semantic_layer_version CASCADE;")
