"""Validate parsed Excel rows — Phase 1 fail-whole-file semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.ingestion.excel_parser import ParsedExcel


@dataclass(frozen=True)
class ValidatedRow:
    """Normalized row ready for dimension resolution."""

    row_index: int
    amount: Decimal
    revenue_date: date
    business_unit: str | None
    division: str | None
    customer: str | None
    revenue_type: str | None
    customer_name_common: str | None = None


@dataclass
class ValidationResult:
    errors: list[dict[str, Any]]
    rows: list[ValidatedRow]


REQUIRED_HEADERS = {"amount", "revenue_date"}


def validate_parsed_excel(parsed: ParsedExcel) -> ValidationResult:
    """Return all validation errors; empty rows list if any error exists."""
    errors: list[dict[str, Any]] = []
    header_set = {h for h in parsed.headers if h}
    missing = REQUIRED_HEADERS - header_set
    if missing:
        errors.append(
            {
                "row": None,
                "column": None,
                "message": f"Missing required columns: {', '.join(sorted(missing))}",
            }
        )
        return ValidationResult(errors=errors, rows=[])

    col_index = {h: i for i, h in enumerate(parsed.headers)}

    validated: list[ValidatedRow] = []
    for i, raw in enumerate(parsed.rows, start=2):
        if _is_empty_row(raw):
            continue
        row_errors, row = _validate_data_row(i, raw, col_index)
        errors.extend(row_errors)
        if row is not None:
            validated.append(row)

    if errors:
        return ValidationResult(errors=errors, rows=[])
    if not validated:
        errors.append(
            {
                "row": None,
                "column": None,
                "message": "No data rows found in the file.",
            }
        )
        return ValidationResult(errors=errors, rows=[])

    return ValidationResult(errors=[], rows=validated)


def _is_empty_row(raw: list[object | None]) -> bool:
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in raw)


def _validate_data_row(
    excel_row: int,
    raw: list[object | None],
    col_index: dict[str, int],
) -> tuple[list[dict[str, Any]], ValidatedRow | None]:
    errors: list[dict[str, Any]] = []

    def cell(name: str) -> object | None:
        idx = col_index.get(name)
        if idx is None or idx >= len(raw):
            return None
        return raw[idx]

    amount_raw = cell("amount")
    date_raw = cell("revenue_date")

    amount: Decimal | None = None
    try:
        if amount_raw is None:
            raise InvalidOperation
        if isinstance(amount_raw, (int, float)) and not isinstance(amount_raw, bool):
            amount = Decimal(str(amount_raw))
        else:
            amount = Decimal(str(amount_raw).strip())
    except (InvalidOperation, ValueError):
        errors.append(
            {
                "row": excel_row,
                "column": "amount",
                "message": "Amount must be a decimal number.",
            }
        )
        amount = None

    if amount is not None and amount <= 0:
        errors.append(
            {
                "row": excel_row,
                "column": "amount",
                "message": "Amount must be positive.",
            }
        )

    rev_date: date | None = None
    dr = date_raw
    if isinstance(dr, datetime):
        rev_date = dr.date()
    elif isinstance(dr, date):
        rev_date = dr
    elif dr is not None:
        s = str(dr).strip()
        try:
            rev_date = date.fromisoformat(s[:10])
        except ValueError:
            errors.append(
                {
                    "row": excel_row,
                    "column": "revenue_date",
                    "message": "revenue_date must be a date (YYYY-MM-DD).",
                }
            )
    else:
        errors.append(
            {
                "row": excel_row,
                "column": "revenue_date",
                "message": "revenue_date is required.",
            }
        )

    if errors:
        return errors, None

    assert amount is not None and rev_date is not None

    def opt_str(name: str) -> str | None:
        v = cell(name)
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    bu = opt_str("business_unit")
    div = opt_str("division")
    if div and not bu:
        errors.append(
            {
                "row": excel_row,
                "column": "business_unit",
                "message": "business_unit is required when division is set.",
            }
        )
        return errors, None

    row = ValidatedRow(
        row_index=excel_row,
        amount=amount,
        revenue_date=rev_date,
        business_unit=bu,
        division=div,
        customer=opt_str("customer"),
        revenue_type=opt_str("revenue_type"),
        customer_name_common=None,
    )
    return [], row
