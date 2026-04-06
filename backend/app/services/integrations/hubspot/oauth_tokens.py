"""Exchange and refresh HubSpot OAuth tokens."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"


async def exchange_authorization_code(code: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.HUBSPOT_CLIENT_ID or not settings.HUBSPOT_CLIENT_SECRET or not settings.HUBSPOT_REDIRECT_URI:
        raise RuntimeError("HubSpot OAuth is not configured")
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.HUBSPOT_CLIENT_ID,
        "client_secret": settings.HUBSPOT_CLIENT_SECRET,
        "redirect_uri": settings.HUBSPOT_REDIRECT_URI,
        "code": code,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(TOKEN_URL, data=data)
    if r.status_code >= 400:
        logger.warning("HubSpot token exchange failed: %s %s", r.status_code, r.text[:500])
        r.raise_for_status()
    return r.json()


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.HUBSPOT_CLIENT_ID or not settings.HUBSPOT_CLIENT_SECRET:
        raise RuntimeError("HubSpot OAuth is not configured")
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.HUBSPOT_CLIENT_ID,
        "client_secret": settings.HUBSPOT_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(TOKEN_URL, data=data)
    if r.status_code >= 400:
        logger.warning("HubSpot token refresh failed: %s %s", r.status_code, r.text[:500])
        r.raise_for_status()
    return r.json()
