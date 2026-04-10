"""Calendar helpers for variance_comment NL intent."""

from datetime import date

from app.services.query_engine.nl_calendar import try_variance_narrative_month_start


def test_two_month_range_uses_later_month() -> None:
    q = "reason for deviation from March 2026 to April 2026 for Acme"
    assert try_variance_narrative_month_start(q) == date(2026, 4, 1)


def test_single_month() -> None:
    q = "variance comment for April 2026 division Europe"
    assert try_variance_narrative_month_start(q) == date(2026, 4, 1)


def test_three_months_ambiguous() -> None:
    q = "comments for Jan 2026, Feb 2026, and Mar 2026"
    assert try_variance_narrative_month_start(q) is None
