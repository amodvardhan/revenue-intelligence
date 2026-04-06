"""Performance-style gate: large row counts through validate_parsed_excel (no DB)."""

from __future__ import annotations

import time

import pytest

from app.services.ingestion.excel_parser import ParsedExcel
from app.services.ingestion.validator import validate_parsed_excel


def test_ten_thousand_rows_validate_under_budget() -> None:
    """Quality gate: 10k-row validation completes quickly (no full xlsx I/O)."""
    n = 10_000
    rows = [[100, "2026-01-01"] for _ in range(n)]
    parsed = ParsedExcel(headers=["amount", "revenue_date"], rows=rows, sheet_name="s")
    t0 = time.perf_counter()
    v = validate_parsed_excel(parsed)
    elapsed = time.perf_counter() - t0
    assert not v.errors
    assert len(v.rows) == n
    assert elapsed < 30.0, f"validation took {elapsed:.2f}s"
