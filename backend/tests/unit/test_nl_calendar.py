"""Explicit calendar month resolution for NL queries."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.query_engine.nl_calendar import (
    merge_explicit_calendar_month_into_plan,
    try_explicit_calendar_month_range,
)


@pytest.mark.parametrize(
    "q,expected",
    [
        ("What is the revenue of WHO in mar'26", (date(2026, 3, 1), date(2026, 3, 31))),
        ("March 2026 revenue for Acme", (date(2026, 3, 1), date(2026, 3, 31))),
        ("total for MAR 26", (date(2026, 3, 1), date(2026, 3, 31))),
        ("2026-03 rollup", (date(2026, 3, 1), date(2026, 3, 31))),
        ("revenue 03/2026", (date(2026, 3, 1), date(2026, 3, 31))),
    ],
)
def test_try_explicit_month(q: str, expected: tuple[date, date]) -> None:
    assert try_explicit_calendar_month_range(q) == expected


def test_try_explicit_month_rejects_compare_language() -> None:
    assert try_explicit_calendar_month_range("March 2026 yoy") is None
    assert try_explicit_calendar_month_range("Mar'26 vs Feb'26") is None


def test_try_explicit_month_rejects_multiple_months() -> None:
    assert try_explicit_calendar_month_range("Mar'26 and Apr'26") is None


def test_merge_clears_clarification_and_sets_rollup() -> None:
    plan = {
        "needs_clarification": True,
        "clarification_prompts": [{"prompt_id": "fiscal_year", "text": "FY?", "choices": []}],
        "intent": "rollup",
        "hierarchy": "org",
        "interpretation": "",
    }
    out = merge_explicit_calendar_month_into_plan(plan, "revenue WHO mar'26")
    assert out["needs_clarification"] is False
    assert out["clarification_prompts"] == []
    assert out["revenue_date_from"] == "2026-03-01"
    assert out["revenue_date_to"] == "2026-03-31"
    assert out["calendar_quarter"] == 1
