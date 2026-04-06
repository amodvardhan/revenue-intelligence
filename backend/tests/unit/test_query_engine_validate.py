"""Story 3.2 — plan validation rejects unsafe / out-of-scope structured intents (no DB)."""

from __future__ import annotations

import pytest

from app.services.query_engine.exceptions import QueryUnsafeError
from app.services.query_engine import service as query_svc


def test_validate_plan_rejects_unsupported_intent() -> None:
    with pytest.raises(QueryUnsafeError, match="Unsupported or missing intent"):
        query_svc._validate_plan(
            {
                "intent": "delete",
                "hierarchy": "org",
                "revenue_date_from": "2026-01-01",
                "revenue_date_to": "2026-01-31",
            }
        )


def test_validate_plan_rejects_date_range_exceeding_envelope() -> None:
    with pytest.raises(QueryUnsafeError, match="Date range exceeds"):
        query_svc._validate_plan(
            {
                "intent": "rollup",
                "hierarchy": "org",
                "revenue_date_from": "2010-01-01",
                "revenue_date_to": "2030-01-01",
            }
        )
