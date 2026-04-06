"""Async HubSpot CRM API client with basic 429 backoff."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.services.integrations.hubspot.constants import DEAL_PROPERTIES, HUBSPOT_API_BASE

logger = logging.getLogger(__name__)


class HubspotApiClient:
    def __init__(self, access_token: str) -> None:
        self._token = access_token
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        max_retries: int = 5,
    ) -> httpx.Response:
        url = f"{HUBSPOT_API_BASE}{path}"
        delay = 1.0
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(max_retries):
                r = await client.request(
                    method,
                    url,
                    headers=self._headers,
                    params=params,
                    json=json_body,
                )
                if r.status_code != 429:
                    return r
                retry_after = r.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else delay
                logger.info("HubSpot rate limit; sleeping %.1fs", wait)
                await asyncio.sleep(wait)
                delay = min(delay * 2, 60.0)
        raise RuntimeError("HubSpot rate limit retries exhausted")

    async def list_deals_page(self, *, limit: int = 100, after: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": limit,
            "properties": ",".join(DEAL_PROPERTIES),
            "associations": "company",
        }
        if after:
            params["after"] = after
        r = await self._request("GET", "/crm/v3/objects/deals", params=params)
        r.raise_for_status()
        return r.json()

    async def get_deal_company_ids(self, deal_id: str) -> list[str]:
        """Return associated company HubSpot ids for a deal."""
        r = await self._request(
            "GET",
            f"/crm/v3/objects/deals/{deal_id}/associations/companies",
        )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        return [str(x.get("id")) for x in results if x.get("id")]

    async def search_deals_modified_after(
        self, *, after_ms: int, limit: int = 100, after_cursor: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "hs_lastmodifieddate",
                            "operator": "GT",
                            "value": str(after_ms),
                        }
                    ]
                }
            ],
            "properties": list(DEAL_PROPERTIES),
            "limit": limit,
        }
        if after_cursor:
            body["after"] = after_cursor
        r = await self._request("POST", "/crm/v3/objects/deals/search", json_body=body)
        r.raise_for_status()
        return r.json()
