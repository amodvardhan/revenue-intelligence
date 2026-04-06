"""Unit tests for analytics service helpers (coverage for app/services/analytics/service.py)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.analytics.service import _amount_str, _period_label, _pct_str, _resolve_org_scope


def test_amount_str_plain_decimal() -> None:
    assert _amount_str(Decimal("12345.6789")) == "12345.6789"


def test_pct_str_ratio() -> None:
    assert _pct_str(Decimal("1"), Decimal("4")) == "0.2500"


def test_pct_str_zero_denominator() -> None:
    assert _pct_str(Decimal("5"), Decimal("0")) == "0.0000"


def test_resolve_org_scope_with_org_id() -> None:
    oid = uuid4()
    other = uuid4()
    assert _resolve_org_scope(oid, {other}) == {oid}


def test_resolve_org_scope_all_accessible() -> None:
    a, b = uuid4(), uuid4()
    assert _resolve_org_scope(None, {a, b}) == {a, b}


@pytest.mark.parametrize("compare", ["mom", "qoq", "yoy"])
def test_period_label_includes_dates(compare: str) -> None:
    label = _period_label(date(2026, 1, 1), date(2026, 3, 31), compare)  # type: ignore[arg-type]
    assert "2026-01-01" in label
    assert "2026-03-31" in label
