"""OpenAI chat completions via httpx — model from settings only."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings
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
  "intent": "rollup" | "compare" | null,
  "hierarchy": "org" | "bu" | "division",
  "org_id": string | null,
  "revenue_date_from": "YYYY-MM-DD" | null,
  "revenue_date_to": "YYYY-MM-DD" | null,
  "compare": "mom" | "qoq" | "yoy" | null,
  "current_period_from": "YYYY-MM-DD" | null,
  "current_period_to": "YYYY-MM-DD" | null,
  "comparison_period_from": "YYYY-MM-DD" | null,
  "comparison_period_to": "YYYY-MM-DD" | null,
  "interpretation": "short canonical sentence",
  "calendar_quarter": 1 | 2 | 3 | 4 | null
}

Rules:
- Use calendar quarters: Q1 Jan–Mar, Q2 Apr–Jun, Q3 Jul–Sep, Q4 Oct–Dec.
- If the user names a quarter (e.g. Q3) without a year, set needs_clarification true, set calendar_quarter (required) to 1–4, and ask fiscal_year with two plausible calendar years (current and previous). Omitting calendar_quarter breaks follow-up resolution.
- For "last month", "previous month", or a single named month without a year: set intent rollup and fill revenue_date_from / revenue_date_to for that one calendar month. Do not use fiscal_year + null calendar_quarter for that case.
- For rollup intent, set revenue_date_from and revenue_date_to inclusive.
- For compare intent, set all four period dates and compare (yoy unless user asked otherwise).
- Never emit SQL. Never invent tables.
"""


async def complete_nl_plan(user_question: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise LlmUnavailableError("OpenAI API key is not configured")
    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_question},
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
