"""Phase 6 — Enterprise SSO, federated identity, security settings, audit export permissions."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260406_0006"
down_revision: Union[str, None] = "20260406_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_auth VARCHAR(50) NOT NULL DEFAULT 'local';
"""
    )

    op.execute(
        """
CREATE TABLE sso_provider_config (
    sso_provider_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    protocol VARCHAR(20) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    display_name VARCHAR(255),
    oidc_issuer VARCHAR(2048),
    oidc_client_id VARCHAR(512),
    oidc_authorization_endpoint VARCHAR(2048),
    oidc_token_endpoint VARCHAR(2048),
    oidc_jwks_uri VARCHAR(2048),
    saml_entity_id VARCHAR(512),
    saml_metadata_url VARCHAR(2048),
    saml_acs_url_path VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (sso_provider_id),
    CONSTRAINT uq_sso_provider_tenant_protocol UNIQUE (tenant_id, protocol),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE
);
"""
    )
    op.execute("CREATE INDEX idx_sso_provider_tenant ON sso_provider_config (tenant_id);")
    op.execute("ALTER TABLE sso_provider_config ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY sso_provider_config_tenant_isolation ON sso_provider_config
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE tenant_email_domain_allowlist (
    allowlist_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    email_domain VARCHAR(255) NOT NULL,
    created_by_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (allowlist_id),
    CONSTRAINT uq_domain_allowlist_tenant_domain UNIQUE (tenant_id, email_domain),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_user_id) REFERENCES users (user_id)
);
"""
    )
    op.execute("CREATE INDEX idx_domain_allowlist_tenant ON tenant_email_domain_allowlist (tenant_id);")
    op.execute("ALTER TABLE tenant_email_domain_allowlist ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY tenant_email_domain_allowlist_tenant_isolation ON tenant_email_domain_allowlist
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE user_federated_identity (
    federated_id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    protocol VARCHAR(20) NOT NULL,
    idp_issuer VARCHAR(2048) NOT NULL,
    idp_subject VARCHAR(512) NOT NULL,
    email_at_link VARCHAR(320),
    first_login_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    last_login_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (federated_id),
    CONSTRAINT uq_federated_tenant_issuer_subject UNIQUE (tenant_id, idp_issuer, idp_subject),
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE
);
"""
    )
    op.execute("CREATE INDEX idx_federated_user ON user_federated_identity (user_id);")
    op.execute("CREATE INDEX idx_federated_tenant ON user_federated_identity (tenant_id);")
    op.execute("ALTER TABLE user_federated_identity ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY user_federated_identity_tenant_isolation ON user_federated_identity
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE idp_group_role_mapping (
    mapping_id UUID DEFAULT gen_random_uuid() NOT NULL,
    tenant_id UUID NOT NULL,
    idp_group_identifier VARCHAR(512) NOT NULL,
    app_role VARCHAR(50) NOT NULL,
    org_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (mapping_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (org_id) REFERENCES dim_organization (org_id) ON DELETE CASCADE
);
"""
    )
    op.execute("CREATE INDEX idx_idp_group_map_tenant ON idp_group_role_mapping (tenant_id);")
    op.execute("ALTER TABLE idp_group_role_mapping ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY idp_group_role_mapping_tenant_isolation ON idp_group_role_mapping
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE user_permission (
    user_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    permission_code VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, tenant_id, permission_code),
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE
);
"""
    )
    op.execute("CREATE INDEX idx_user_permission_tenant ON user_permission (tenant_id);")
    op.execute("ALTER TABLE user_permission ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY user_permission_tenant_isolation ON user_permission
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
CREATE TABLE tenant_security_settings (
    tenant_id UUID NOT NULL,
    invite_only BOOLEAN NOT NULL DEFAULT FALSE,
    require_sso_for_standard_users BOOLEAN NOT NULL DEFAULT FALSE,
    idle_timeout_minutes INTEGER,
    absolute_timeout_minutes INTEGER,
    retention_notice_label VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (tenant_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE
);
"""
    )
    op.execute("ALTER TABLE tenant_security_settings ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
CREATE POLICY tenant_security_settings_tenant_isolation ON tenant_security_settings
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""
    )

    op.execute(
        """
INSERT INTO tenant_security_settings (tenant_id)
SELECT tenant_id FROM tenants
ON CONFLICT (tenant_id) DO NOTHING;
"""
    )

    op.execute(
        """
INSERT INTO user_permission (user_id, tenant_id, permission_code)
SELECT u.user_id, u.tenant_id, 'audit_export'
FROM users u
JOIN user_org_role uor ON uor.user_id = u.user_id AND uor.role = 'it_admin'
ON CONFLICT DO NOTHING;
"""
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_security_settings CASCADE;")
    op.execute("DROP TABLE IF EXISTS user_permission CASCADE;")
    op.execute("DROP TABLE IF EXISTS idp_group_role_mapping CASCADE;")
    op.execute("DROP TABLE IF EXISTS user_federated_identity CASCADE;")
    op.execute("DROP TABLE IF EXISTS tenant_email_domain_allowlist CASCADE;")
    op.execute("DROP TABLE IF EXISTS sso_provider_config CASCADE;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS primary_auth;")
