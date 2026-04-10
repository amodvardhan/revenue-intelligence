"""Rule-based hints for NL — steers classification without executing raw SQL."""

from __future__ import annotations

import re
from typing import Any

# Strong signals for Phase 7 variance narratives (revenue_variance_comment), not generic revenue totals.
_VARIANCE_NARRATIVE = re.compile(
    r"(?is)"
    r"\b("
    r"reason|reasons|why|explain|explanation|narrative|comment|comments|"
    r"deviat|deviation|variance\s+comment|mom\s+reason|what\s+happened"
    r")\b"
)

# Avoid stealing generic "total revenue" questions.
def looks_like_variance_narrative_question(question: str) -> bool:
    """True when the user likely wants stored variance narrative text, not a numeric rollup."""
    if not (question or "").strip():
        return False
    return bool(_VARIANCE_NARRATIVE.search(question))


def augment_question_for_llm(user_question: str) -> str:
    """Prefix a compact hint so the model chooses intent variance_comment when appropriate."""
    if not looks_like_variance_narrative_question(user_question):
        return user_question
    return (
        "[Classification: If the user asks for reasons, comments, or narratives about revenue "
        "change, deviation, or month-over-month variance, use intent variance_comment — not rollup "
        "or compare.]\n\n"
        + user_question.strip()
    )


def coerce_plan_toward_variance_if_needed(plan: dict[str, Any], question: str) -> dict[str, Any]:
    """
    When the model returns rollup/compare for a clearly narrative question, recover variance_comment
    so execution does not fail on irrelevant numeric intents.
    """
    if not looks_like_variance_narrative_question(question):
        return plan
    intent = plan.get("intent")
    if intent == "variance_comment":
        return plan
    if intent not in ("rollup", "compare", None):
        return plan
    out = dict(plan)
    out["intent"] = "variance_comment"
    out["needs_clarification"] = False
    out["clarification_prompts"] = []
    # Drop numeric-only fields that would confuse validators.
    for k in (
        "revenue_date_from",
        "revenue_date_to",
        "current_period_from",
        "current_period_to",
        "comparison_period_from",
        "comparison_period_to",
        "compare",
    ):
        out.pop(k, None)
    if out.get("hierarchy") not in ("org", "bu", "division", "customer"):
        out["hierarchy"] = "org"
    return out
