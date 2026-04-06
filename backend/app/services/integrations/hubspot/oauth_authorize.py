"""Build HubSpot OAuth authorization URL."""

from __future__ import annotations

from urllib.parse import urlencode

from app.core.config import get_settings
from app.services.integrations.hubspot.constants import DEFAULT_SCOPES, HUBSPOT_AUTH_BASE


def build_authorization_url(*, state: str) -> str:
    settings = get_settings()
    if not settings.HUBSPOT_CLIENT_ID or not settings.HUBSPOT_REDIRECT_URI:
        raise RuntimeError("HubSpot OAuth is not configured")
    q = urlencode(
        {
            "client_id": settings.HUBSPOT_CLIENT_ID,
            "redirect_uri": settings.HUBSPOT_REDIRECT_URI,
            "scope": DEFAULT_SCOPES,
            "state": state,
        }
    )
    return f"{HUBSPOT_AUTH_BASE}?{q}"
