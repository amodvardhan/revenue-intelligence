"""Entity phrase extraction and fuzzy resolution helpers."""

from __future__ import annotations

from app.services.query_engine.nl_calendar import strip_inline_calendar_expressions as strip_cal
from app.services.query_engine.nl_entity import (
    extract_business_unit_focus_phrase,
    extract_entity_focus_phrase,
)


def test_strip_calendar_alias() -> None:
    assert "mar'26" not in strip_cal("What was the Mar'26 revenue for Acme").lower()


def test_extract_revenue_for() -> None:
    q = "What was the Mar'26 revenue for World health Orgnization"
    assert extract_entity_focus_phrase(q) == "World health Orgnization"


def test_extract_revenue_of_who() -> None:
    q = "What is the revenue of WHO in mar'26"
    assert extract_entity_focus_phrase(q) == "WHO"


def test_extract_none_when_no_for_or_of() -> None:
    assert extract_entity_focus_phrase("Q3 2026 revenue by business unit") is None


def test_extract_bu_growth_question() -> None:
    q = "overall growth of the BU e-zest digital solutions"
    assert extract_business_unit_focus_phrase(q) == "e-zest digital solutions"
