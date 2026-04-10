"""Entity phrase normalization for NL resolution."""

from app.services.query_engine.nl_entity import normalize_entity_resolution_phrase


def test_strips_overall_and_fiscal_year() -> None:
    s = "e-zest digital solution overall this fiscal year"
    assert normalize_entity_resolution_phrase(s) == "e-zest digital solution"


def test_strips_in_total() -> None:
    assert normalize_entity_resolution_phrase("Acme Corp in total") == "Acme Corp"
