"""Phase 3 — NL → structured plan → validate → analytics execution (no raw LLM SQL)."""

from app.services.query_engine.service import run_natural_language_query

__all__ = ["run_natural_language_query"]
