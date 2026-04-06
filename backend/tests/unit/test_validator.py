"""Unit tests for ingestion validator (no database)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services.ingestion.excel_parser import ParsedExcel
from app.services.ingestion.validator import validate_parsed_excel


def test_missing_required_column_amount() -> None:
    parsed = ParsedExcel(
        headers=["revenue_date"],
        rows=[["2026-01-01"]],
        sheet_name="s",
    )
    r = validate_parsed_excel(parsed)
    assert r.rows == []
    assert any("amount" in e["message"].lower() or "Missing required" in e["message"] for e in r.errors)


def test_negative_amount_rejected() -> None:
    parsed = ParsedExcel(
        headers=["amount", "revenue_date"],
        rows=[[-100, "2026-01-01"]],
        sheet_name="s",
    )
    r = validate_parsed_excel(parsed)
    assert r.rows == []
    assert any("positive" in e["message"].lower() for e in r.errors)


def test_zero_amount_rejected() -> None:
    parsed = ParsedExcel(
        headers=["amount", "revenue_date"],
        rows=[[0, "2026-01-01"]],
        sheet_name="s",
    )
    r = validate_parsed_excel(parsed)
    assert r.rows == []
    assert any("positive" in e["message"].lower() for e in r.errors)


def test_valid_row() -> None:
    parsed = ParsedExcel(
        headers=["amount", "revenue_date", "business_unit", "division"],
        rows=[[100.5, "2026-01-15", "BU1", "Div1"]],
        sheet_name="s",
    )
    r = validate_parsed_excel(parsed)
    assert not r.errors
    assert len(r.rows) == 1
    assert r.rows[0].amount == Decimal("100.5")
    assert r.rows[0].revenue_date == date(2026, 1, 15)


def test_headers_only_no_data_rows() -> None:
    parsed = ParsedExcel(
        headers=["amount", "revenue_date"],
        rows=[],
        sheet_name="s",
    )
    r = validate_parsed_excel(parsed)
    assert r.rows == []
    assert any("No data rows" in e["message"] for e in r.errors)


def test_division_without_business_unit_rejected() -> None:
    parsed = ParsedExcel(
        headers=["amount", "revenue_date", "business_unit", "division"],
        rows=[[100, "2026-01-01", None, "Div1"]],
        sheet_name="s",
    )
    r = validate_parsed_excel(parsed)
    assert r.rows == []
    assert any("business_unit" in e["message"].lower() for e in r.errors)


@pytest.mark.parametrize(
    "date_val",
    ["2026-06-01", "2026-06-01T00:00:00"],
)
def test_date_iso_variants(date_val: str) -> None:
    parsed = ParsedExcel(
        headers=["amount", "revenue_date"],
        rows=[[50, date_val]],
        sheet_name="s",
    )
    r = validate_parsed_excel(parsed)
    assert not r.errors
    assert r.rows[0].revenue_date == date(2026, 6, 1)
