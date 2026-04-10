"""Story 3.1 — semantic artifact load, version label, content hash (no DB)."""

from __future__ import annotations

import pytest

from app.core.semantic_layer import (
    clear_bundle_cache,
    format_nl_system_addendum,
    load_semantic_bundle,
)


@pytest.fixture(autouse=True)
def _reset_semantic_cache() -> None:
    clear_bundle_cache()
    yield
    clear_bundle_cache()


def test_semantic_bundle_has_version_label_and_stable_hash() -> None:
    b = load_semantic_bundle()
    assert b.version_label
    assert isinstance(b.version_label, str)
    assert len(b.content_sha256) == 64
    assert b.data.get("metrics", {}).get("total_revenue", {}).get("canonical") == "fact_revenue.amount"


def test_semantic_bundle_includes_phase5_forecast_metric() -> None:
    """Story 5.3 — NL semantic layer exposes forecast measure aligned with fact_forecast."""
    b = load_semantic_bundle()
    fc = b.data.get("metrics", {}).get("forecast_total", {})
    assert fc.get("canonical") == "fact_forecast.amount"
    assert fc.get("aggregation") == "sum"


def test_semantic_bundle_includes_customer_dimension_and_nl_grounding() -> None:
    b = load_semantic_bundle()
    cust = b.data.get("dimensions", {}).get("customer", {})
    assert cust.get("canonical_key") == "dimension.customer"
    grounding = b.data.get("nl_grounding", {})
    assert grounding.get("primary_fact_table") == "fact_revenue"
    assert grounding.get("foreign_keys", {}).get("customer_id") == "dim_customer"
    text = format_nl_system_addendum(b.data)
    assert "dim_customer" in text
    assert "customer_id" in text


def test_semantic_bundle_includes_variance_comment_grounding() -> None:
    b = load_semantic_bundle()
    vc = b.data.get("nl_intents", {}).get("variance_comment", {})
    assert vc.get("physical_table") == "revenue_variance_comment"
    assert vc.get("text_field") == "comment_text"
    vn = b.data.get("nl_grounding", {}).get("variance_narrative", {})
    assert vn.get("table") == "revenue_variance_comment"
    assert vn.get("time_key") == "revenue_month"
    text = format_nl_system_addendum(b.data)
    assert "revenue_variance_comment" in text
    assert "comment_text" in text
    assert "variance_comment" in text


def test_semantic_bundle_is_cached() -> None:
    a = load_semantic_bundle()
    b = load_semantic_bundle()
    assert a is b
