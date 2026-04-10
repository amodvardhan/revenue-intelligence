"""OpenAI chat completions via httpx — model from settings only."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.semantic_layer import format_nl_system_addendum, load_semantic_bundle
from app.services.query_engine.exceptions import LlmUnavailableError

logger = logging.getLogger(__name__)

SYSTEM = """You interpret enterprise revenue questions. Reply with a single JSON object only (no markdown).

Schema:
{
  "needs_clarification": boolean,
  "clarification_prompts": [
    {
      "prompt_id": "fiscal_year",
      "text": "string",
      "choices": [{"id": "2025", "label": "FY 2025"}, {"id": "2026", "label": "FY 2026"}]
    }
  ],
  "intent": "rollup" | "compare" | "variance_comment" | null,
  "hierarchy": "org" | "bu" | "division" | "customer",
  "org_id": string | null,
  "customer_name": string | null,
  "business_unit_name": string | null,
  "division_name": string | null,
  "revenue_date_from": "YYYY-MM-DD" | null,
  "revenue_date_to": "YYYY-MM-DD" | null,
  "compare": "mom" | "qoq" | "yoy" | null,
  "current_period_from": "YYYY-MM-DD" | null,
  "current_period_to": "YYYY-MM-DD" | null,
  "comparison_period_from": "YYYY-MM-DD" | null,
  "comparison_period_to": "YYYY-MM-DD" | null,
  "variance_revenue_month": "YYYY-MM-DD" | null,
  "interpretation": "short canonical sentence",
  "calendar_quarter": 1 | 2 | 3 | 4 | null
}

Rules:
- Use calendar quarters: Q1 Jan–Mar, Q2 Apr–Jun, Q3 Jul–Sep, Q4 Oct–Dec.
- If the user names a quarter (e.g. Q3) without a year, set needs_clarification true, set calendar_quarter (required) to 1–4, and ask fiscal_year with two plausible calendar years (current and previous). Omitting calendar_quarter breaks follow-up resolution.
- If the user names a calendar month together with any year — including short forms (Mar'26, Mar 26, March 2026, 03/2026) — set needs_clarification false, intent rollup, and revenue_date_from / revenue_date_to for that calendar month only. Never ask for fiscal year or "which FY" for March when the calendar year is already stated; map two-digit years as 20xx (e.g. 26 → 2026).
- Exception: if the user asks for reasons, comments, narratives, or explanations for revenue deviation / variance / month-over-month change, use intent variance_comment instead of rollup or compare. Set hierarchy to the narrowest scope they name: customer, division, bu, or org. Fill division_name or business_unit_name when they name those entities.
- For variance_comment: set variance_revenue_month to the first day of the calendar month that the narrative applies to. If they give two months (e.g. "March 2026 to April 2026"), the narrative month is the later month (April → 2026-04-01). If they give one month, use that month. These narratives are stored per customer (and optional BU/division scope) — prefer hierarchy "customer" when they name a customer.
- For "last month", "previous month", or a single named month without a year: set intent rollup and fill revenue_date_from / revenue_date_to for that one calendar month. Do not use fiscal_year + null calendar_quarter for that case.
- For rollup intent, set revenue_date_from and revenue_date_to inclusive.
- For compare intent, set all four period dates and compare (yoy unless user asked otherwise).
- When the user asks for revenue for a named customer, client, or account (e.g. "for Acme", "revenue of WHO"), set hierarchy to "customer" and customer_name to the name as stated (normalized wording is OK). When they name an organization only, use hierarchy "org" or leave org_id null for the server to match.
- **Organization vs BU:** Legal entity / company names (e.g. "e-Zest Digital Solutions") and phrases like "overall", "company-wide", or "this fiscal year" refer to **organization**-level rollups — set hierarchy **"org"**, leave business_unit_name null, and put the company name in customer_name only if it is actually a customer; otherwise rely on the question text for the server to match **dim_organization.org_name**. Do **not** put an organization name in business_unit_name unless the user explicitly says business unit / BU.
- When they name a business unit (BU), set hierarchy to "bu", set business_unit_name to the BU name (strip a leading "BU" if redundant), and leave customer_name null unless they also name a customer.
- When they name a division, set hierarchy to "division" and division_name as stated.
- Never emit SQL. Never invent tables.
"""


async def complete_nl_plan(user_question: str) -> dict[str, Any]:
    from app.services.query_engine.nl_heuristics import augment_question_for_llm

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise LlmUnavailableError("OpenAI API key is not configured")
    bundle = load_semantic_bundle()
    addendum = format_nl_system_addendum(bundle.data)
    system_content = f"{SYSTEM}\n\n{addendum}" if addendum else SYSTEM
    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": augment_question_for_llm(user_question)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.QUERY_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as e:
        logger.warning("OpenAI HTTP error: %s", e)
        raise LlmUnavailableError("Language model request failed") from e
    if r.status_code >= 400:
        logger.warning("OpenAI status %s: %s", r.status_code, r.text[:500])
        raise LlmUnavailableError("Language model returned an error")
    try:
        body = r.json()
        text = body["choices"][0]["message"]["content"]
        return json.loads(text)
    except (KeyError, json.JSONDecodeError, IndexError) as e:
        logger.warning("OpenAI parse error: %s", e)
        raise LlmUnavailableError("Invalid response from language model") from e
