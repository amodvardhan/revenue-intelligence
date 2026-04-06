"""Story 3.1 — semantic artifact load, version label, content hash (no DB)."""

from __future__ import annotations

import pytest

from app.core.semantic_layer import clear_bundle_cache, load_semantic_bundle


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


def test_semantic_bundle_is_cached() -> None:
    a = load_semantic_bundle()
    b = load_semantic_bundle()
    assert a is b
