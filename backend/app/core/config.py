"""Pydantic Settings — single source for environment-derived configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    DATABASE_URL: str = Field(
        ...,
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )
    REDIS_URL: str = Field(
        ...,
        description="Celery broker / Redis",
    )
    SECRET_KEY: str = Field(..., min_length=16)

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    MAX_QUERY_ROWS: int = 10_000
    QUERY_TIMEOUT_SECONDS: int = 30

    ENABLE_NL_QUERY: bool = True

    ENABLE_HUBSPOT: bool = False

    ENABLE_PHASE5: bool = False

    ENABLE_PHASE7: bool = False

    ENABLE_SSO: bool = True
    """Public URL of this API (no trailing slash) — used for OIDC redirect_uri and SAML ACS."""
    PUBLIC_API_BASE_URL: str = "http://127.0.0.1:8000"
    """Browser URL of the SPA — SSO callbacks redirect here with access_token."""
    FRONTEND_PUBLIC_BASE_URL: str = "http://localhost:5173"
    """OIDC client secret for token exchange (dedicated deployment / env-only secret)."""
    OIDC_CLIENT_SECRET: str | None = None
    """Optional PEM for SAML SP signing (HTTP-Redirect AuthnRequest)."""
    SAML_SP_PRIVATE_KEY_PEM: str | None = None
    AUDIT_EXPORT_MAX_ROWS: int = 500_000
    SSO_CALLBACK_RATE_PER_MINUTE: int = 60

    HUBSPOT_CLIENT_ID: str | None = None
    HUBSPOT_CLIENT_SECRET: str | None = None
    """Backend OAuth callback URL registered in the HubSpot developer app."""
    HUBSPOT_REDIRECT_URI: str | None = None
    """Where the browser lands after OAuth (query flags for success/error)."""
    HUBSPOT_FRONTEND_REDIRECT_BASE: str = "http://localhost:5173/integrations/hubspot"

    ALLOW_REGISTRATION: bool = True

    INGEST_SYNC_MAX_BYTES: int = Field(
        default=5 * 1024 * 1024,
        description="Files at or below this size may be processed synchronously.",
    )
    INGEST_ASYNC_MIN_BYTES: int = Field(
        default=5 * 1024 * 1024,
        description="Files above this threshold enqueue async ingestion.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
