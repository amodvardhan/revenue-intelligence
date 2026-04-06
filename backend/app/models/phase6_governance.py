"""Phase 6 — SSO, federated identity, permissions, tenant security settings."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.core.database import Base


class SsoProviderConfig(Base):
    __tablename__ = "sso_provider_config"
    __table_args__ = (
        UniqueConstraint("tenant_id", "protocol", name="uq_sso_provider_tenant_protocol"),
        Index("idx_sso_provider_tenant", "tenant_id"),
    )

    sso_provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oidc_issuer: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    oidc_client_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    oidc_authorization_endpoint: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    oidc_token_endpoint: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    oidc_jwks_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    saml_entity_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    saml_metadata_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    saml_acs_url_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class TenantEmailDomainAllowlist(Base):
    __tablename__ = "tenant_email_domain_allowlist"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email_domain", name="uq_domain_allowlist_tenant_domain"),
        Index("idx_domain_allowlist_tenant", "tenant_id"),
    )

    allowlist_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    email_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class UserFederatedIdentity(Base):
    __tablename__ = "user_federated_identity"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idp_issuer", "idp_subject", name="uq_federated_tenant_issuer_subject"),
        Index("idx_federated_user", "user_id"),
        Index("idx_federated_tenant", "tenant_id"),
    )

    federated_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)
    idp_issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    idp_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    email_at_link: Mapped[str | None] = mapped_column(String(320), nullable=True)
    first_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdpGroupRoleMapping(Base):
    __tablename__ = "idp_group_role_mapping"
    __table_args__ = (Index("idx_idp_group_map_tenant", "tenant_id"),)

    mapping_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    idp_group_identifier: Mapped[str] = mapped_column(String(512), nullable=False)
    app_role: Mapped[str] = mapped_column(String(50), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dim_organization.org_id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class UserPermission(Base):
    __tablename__ = "user_permission"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "tenant_id", "permission_code"),
        Index("idx_user_permission_tenant", "tenant_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    permission_code: Mapped[str] = mapped_column(String(64), nullable=False)


class TenantSecuritySettings(Base):
    __tablename__ = "tenant_security_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), primary_key=True
    )
    invite_only: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    require_sso_for_standard_users: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    idle_timeout_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    absolute_timeout_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_notice_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
