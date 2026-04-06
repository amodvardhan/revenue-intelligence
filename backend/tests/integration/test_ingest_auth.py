"""Integration: ingest endpoints enforce authentication."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_without_token_returns_401(async_client: AsyncClient) -> None:
    r = await async_client.post(
        "/api/v1/ingest/uploads",
        data={"org_id": str(uuid4())},
        files={
            "file": (
                "sample.xlsx",
                b"not-valid-xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_batches_list_without_token_returns_401(async_client: AsyncClient) -> None:
    r = await async_client.get("/api/v1/ingest/batches")
    assert r.status_code == 401
