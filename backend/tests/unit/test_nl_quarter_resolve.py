"""Quarter extraction for fiscal_year clarification (LLM shape variance)."""

from __future__ import annotations

import pytest

from app.services.query_engine.exceptions import QueryUnsafeError
from datetime import date

from app.services.query_engine.service import (
    _extract_calendar_quarter,
    _last_month_range_for_year_choice,
    _merge_year_into_plan,
)


def test_extract_from_int_and_float() -> None:
    assert _extract_calendar_quarter({"calendar_quarter": 3}) == 3
    assert _extract_calendar_quarter({"calendar_quarter": 2.0}) == 2


def test_extract_from_q_prefix_and_aliases() -> None:
    assert _extract_calendar_quarter({"calendar_quarter": "Q4"}) == 4
    assert _extract_calendar_quarter({"quarter": "q1"}) == 1
    assert _extract_calendar_quarter({"fiscal_quarter": "3"}) == 3


def test_extract_from_partial_dates_when_quarter_missing() -> None:
    assert _extract_calendar_quarter({"revenue_date_from": "2026-07-15"}) == 3
    assert _extract_calendar_quarter({"current_period_from": "2025-01-31"}) == 1


def test_extract_raises_when_nothing_to_infer() -> None:
    with pytest.raises(QueryUnsafeError):
        _extract_calendar_quarter({})


def test_merge_year_rollup_infers_quarter_from_single_date() -> None:
    out = _merge_year_into_plan(
        {
            "intent": "rollup",
            "hierarchy": "bu",
            "revenue_date_from": "2026-08-01",
            "interpretation": "Q3 revenue",
        },
        2026,
    )
    assert out["revenue_date_from"] == "2026-07-01"
    assert out["revenue_date_to"] == "2026-09-30"


def test_last_month_range_for_year_choice() -> None:
    anchor = date(2026, 4, 6)
    assert _last_month_range_for_year_choice(2025, anchor=anchor) == (
        date(2025, 12, 1),
        date(2025, 12, 31),
    )
    assert _last_month_range_for_year_choice(2026, anchor=anchor) == (
        date(2026, 3, 1),
        date(2026, 3, 31),
    )
    assert _last_month_range_for_year_choice(2027, anchor=anchor) == (
        date(2026, 12, 1),
        date(2026, 12, 31),
    )


def test_merge_year_rollup_last_month_without_quarter() -> None:
    anchor = date(2026, 4, 6)
    out = _merge_year_into_plan(
        {
            "intent": "rollup",
            "hierarchy": "bu",
            "interpretation": "Revenue for last month",
        },
        2026,
        original_question="What's the last month revenue for WHO",
        _date_anchor=anchor,
    )
    assert out["revenue_date_from"] == "2026-03-01"
    assert out["revenue_date_to"] == "2026-03-31"
