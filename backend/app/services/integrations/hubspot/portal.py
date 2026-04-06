"""Resolve HubSpot portal id from an access token."""

from __future__ import annotations

from typing import Any

import httpx


async def fetch_portal_id(access_token: str) -> str | None:
    """GET /oauth/v1/access-tokens/{token} — returns hub_id / portal metadata."""
    url = f"https://api.hubapi.com/oauth/v1/access-tokens/{access_token}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
    if r.status_code >= 400:
        return None
    data: dict[str, Any] = r.json()
    hub_id = data.get("hub_id") or data.get("token_id")
    if hub_id is not None:
        return str(hub_id)
    return None
