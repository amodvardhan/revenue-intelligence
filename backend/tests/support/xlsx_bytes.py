"""Build minimal .xlsx bytes for ingestion tests."""

from __future__ import annotations

from io import BytesIO

import openpyxl


def minimal_revenue_xlsx(*, with_unknown_bu: bool = False) -> bytes:
    """Two data rows, amount + revenue_date; optional bad business_unit name."""
    wb = openpyxl.Workbook()
    ws = wb.active
    if with_unknown_bu:
        ws.append(["amount", "revenue_date", "business_unit"])
        ws.append([100, "2026-01-15", "___NO_SUCH_BU___"])
    else:
        ws.append(["amount", "revenue_date"])
        ws.append([100, "2026-01-15"])
        ws.append([200, "2026-01-16"])
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
