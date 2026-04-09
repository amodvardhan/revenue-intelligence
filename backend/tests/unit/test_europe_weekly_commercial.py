"""EUROPE Weekly Commercial parser — layout detection and value rows only (D2)."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import openpyxl
import pytest

from app.services.ingestion.europe_weekly_commercial import (
    looks_like_europe_weekly_sheet,
    try_parse_europe_weekly_commercial,
)
from tests.support.xlsx_bytes import minimal_revenue_xlsx


def _europe_workbook_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append([None, None, None, None, None])
    ws.append(
        [
            None,
            "Sr. No.",
            "Customer Name",
            "Customer Name",
            datetime(2025, 12, 1, 0, 0),
            datetime(2026, 1, 1, 0, 0),
        ]
    )
    ws.append([None, 1, "Creiss Systems GmbH", "Creiss", 1000, 2000])
    ws.append([None, None, "Creiss Systems GmbH", "Creiss", 50, 25])
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_minimal_phase1_xlsx_not_detected_as_europe() -> None:
    assert try_parse_europe_weekly_commercial(minimal_revenue_xlsx()) is None


def test_looks_like_header_row() -> None:
    rows = [
        tuple(),
        (None, "Sr. No.", "Customer Name", "Customer Name", "Dec 2025", "Jan 2026"),
    ]
    assert looks_like_europe_weekly_sheet(rows) is True


def test_parse_europe_emits_facts_skips_delta_row() -> None:
    content = _europe_workbook_bytes()
    res = try_parse_europe_weekly_commercial(content)
    assert res is not None
    assert not res.errors
    assert len(res.rows) == 2
    assert res.rows[0].customer == "Creiss Systems GmbH"
    assert res.rows[0].customer_name_common == "Creiss"
    assert res.rows[0].amount == pytest.approx(1000)
    assert res.rows[1].amount == pytest.approx(2000)
