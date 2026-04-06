"""Load HubSpot tokens and refresh access token when expired."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hubspot_integration import HubspotConnection
from app.services.integrations.hubspot.crypto_bundle import decrypt_token_bundle, encrypt_token_bundle
from app.services.integrations.hubspot.oauth_tokens import refresh_access_token

logger = logging.getLogger(__name__)


async def get_connection(session: AsyncSession, tenant_id: UUID) -> HubspotConnection | None:
    res = await session.execute(select(HubspotConnection).where(HubspotConnection.tenant_id == tenant_id))
    return res.scalar_one_or_none()


async def ensure_fresh_access_token(
    session: AsyncSession,
    conn: HubspotConnection,
) -> str:
    """Return a usable access token; refresh and persist when near expiry."""
    if not conn.encrypted_token_bundle:
        raise ValueError("HubSpot connection has no tokens")
    bundle = decrypt_token_bundle(conn.encrypted_token_bundle)
    access = bundle.get("access_token")
    refresh = bundle.get("refresh_token")
    if not access or not refresh:
        raise ValueError("Invalid token bundle")

    expires_at = conn.token_expires_at
    now = datetime.now(tz=UTC)
    if expires_at and expires_at <= now + timedelta(minutes=2):
        try:
            new_tokens = await refresh_access_token(refresh)
        except Exception:
            logger.exception("HubSpot refresh failed for tenant %s", conn.tenant_id)
            conn.status = "token_refresh_failed"
            conn.last_error = "OAuth refresh failed — reconnect HubSpot."
            await session.flush()
            raise

        access = new_tokens["access_token"]
        if "refresh_token" in new_tokens:
            refresh = new_tokens["refresh_token"]
        expires_in = int(new_tokens.get("expires_in", 1800))
        bundle = {"access_token": access, "refresh_token": refresh}
        conn.encrypted_token_bundle = encrypt_token_bundle(bundle)
        conn.token_expires_at = now + timedelta(seconds=expires_in)
        conn.last_token_refresh_at = now
        conn.status = "connected"
        conn.last_error = None
        await session.flush()

    return access
