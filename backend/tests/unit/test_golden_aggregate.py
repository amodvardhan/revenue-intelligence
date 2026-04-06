"""Golden-style validation: known Excel content → expected totals (no DB)."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import openpyxl
import pytest

from app.services.ingestion.excel_parser import parse_excel
from app.services.ingestion.validator import validate_parsed_excel


def _build_workbook_bytes() -> bytes:
    """Minimal workbook with two data rows and known amounts."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["amount", "revenue_date", "business_unit", "division"])
    ws.append([1000, "2026-01-01", "North", "Retail"])
    ws.append([234.56, "2026-02-01", "North", "Retail"])
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_parse_and_validate_aggregate_matches_expected() -> None:
    content = _build_workbook_bytes()
    parsed = parse_excel(content)
    v = validate_parsed_excel(parsed)
    assert not v.errors
    assert len(v.rows) == 2
    total = sum((r.amount for r in v.rows), Decimal(0))
    assert total == Decimal("1234.56")


def test_extra_columns_ignored() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["amount", "revenue_date", "notes", "extra"])
    ws.append([10, "2026-01-01", "hello", "ignored"])
    bio = BytesIO()
    wb.save(bio)
    v = validate_parsed_excel(parse_excel(bio.getvalue()))
    assert not v.errors
    assert len(v.rows) == 1
