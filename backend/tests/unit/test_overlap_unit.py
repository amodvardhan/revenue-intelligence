"""Unit tests for overlap helpers (mocked session)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.ingestion.overlap import scope_has_overlap


@pytest.mark.asyncio
async def test_scope_has_overlap_true_when_completed_batch_exists() -> None:
    tid, oid = uuid4(), uuid4()
    session = AsyncMock()
    hit = MagicMock()
    hit.scalar_one_or_none.return_value = uuid4()
    session.execute = AsyncMock(return_value=hit)

    assert (
        await scope_has_overlap(
            session,
            tenant_id=tid,
            scope_org_id=oid,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
        )
        is True
    )


@pytest.mark.asyncio
async def test_scope_has_overlap_true_when_fact_exists_second_query() -> None:
    tid, oid = uuid4(), uuid4()
    session = AsyncMock()
    miss = MagicMock()
    miss.scalar_one_or_none.return_value = None
    hit = MagicMock()
    hit.scalar_one_or_none.return_value = uuid4()
    session.execute = AsyncMock(side_effect=[miss, hit])

    assert (
        await scope_has_overlap(
            session,
            tenant_id=tid,
            scope_org_id=oid,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
        )
        is True
    )


@pytest.mark.asyncio
async def test_scope_has_overlap_false_when_no_match() -> None:
    tid, oid = uuid4(), uuid4()
    session = AsyncMock()
    miss = MagicMock()
    miss.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(side_effect=[miss, miss])

    assert (
        await scope_has_overlap(
            session,
            tenant_id=tid,
            scope_org_id=oid,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
        )
        is False
    )
