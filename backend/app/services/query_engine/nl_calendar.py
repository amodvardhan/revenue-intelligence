"""Deterministic calendar hints for NL queries — reduces spurious fiscal-year prompts."""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Any

# Month name / abbreviation → month number (longest keys matched first in alternation)
_MONTH_ALIASES: tuple[tuple[str, int], ...] = (
    ("september", 9),
    ("october", 10),
    ("november", 11),
    ("december", 12),
    ("january", 1),
    ("february", 2),
    ("march", 3),
    ("april", 4),
    ("june", 6),
    ("july", 7),
    ("august", 8),
    ("sept", 9),
    ("oct", 10),
    ("nov", 11),
    ("dec", 12),
    ("jan", 1),
    ("feb", 2),
    ("mar", 3),
    ("apr", 4),
    ("may", 5),
    ("jun", 6),
    ("jul", 7),
    ("aug", 8),
)

_MONTH_ALT = "|".join(
    re.escape(k) for k, _ in sorted(_MONTH_ALIASES, key=lambda x: -len(x[0]))
)

# Explicit month + year: Mar'26, march 2026, Mar 26 (year), etc.
_MONTH_YEAR = re.compile(
    rf"\b({_MONTH_ALT})\s*['']?\s*(\d{{2,4}})\b",
    re.IGNORECASE,
)

# ISO-like month: 2026-03 or 2026-03-01 (use month only)
_ISO_MONTH = re.compile(r"\b(20\d{2})-(\d{2})(?:-(\d{2}))?\b")

# Unambiguous numeric month/year: 03/2026, 3/2026, 03-2026
_NUM_MY = re.compile(r"\b(\d{1,2})[/\-](\d{4})\b", re.IGNORECASE)

_COMPARE_RE = re.compile(
    r"\b(yoy|year[-\s]?over[-\s]?year|qoq|mom|compare|versus|vs\.?)\b",
    re.IGNORECASE,
)


def strip_inline_calendar_expressions(text: str) -> str:
    """Remove month/year fragments so downstream parsers can read entity names (e.g. after Mar'26)."""
    if not text:
        return ""
    t = text
    for rx in (_MONTH_YEAR, _ISO_MONTH, _NUM_MY):
        t = rx.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def _two_digit_year(y: int) -> int:
    if y >= 100:
        return y
    return 2000 + y


def _month_last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _span_for_month_year(year: int, month: int) -> tuple[date, date]:
    d1 = _month_last_day(year, month)
    return date(year, month, 1), date(year, month, d1)


def _month_num_from_token(raw_mon: str) -> int | None:
    raw = raw_mon.lower()
    for name, num in sorted(_MONTH_ALIASES, key=lambda x: -len(x[0])):
        if raw == name:
            return num
    for name, num in sorted(_MONTH_ALIASES, key=lambda x: -len(x[0])):
        if len(raw) == 3 and name.startswith(raw):
            return num
    return None


def _parse_month_name_year(m: re.Match[str]) -> tuple[int, int] | None:
    month_num = _month_num_from_token(m.group(1))
    if month_num is None:
        return None
    yi = int(m.group(2))
    year = _two_digit_year(yi)
    return year, month_num


def _all_month_year_spans(text: str) -> list[tuple[date, date]]:
    spans: list[tuple[date, date]] = []
    seen: set[tuple[date, date]] = set()
    for m in _MONTH_YEAR.finditer(text):
        parsed = _parse_month_name_year(m)
        if parsed:
            sp = _span_for_month_year(*parsed)
            if sp not in seen:
                seen.add(sp)
                spans.append(sp)

    for m in _ISO_MONTH.finditer(text):
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            sp = _span_for_month_year(y, mo)
            if sp not in seen:
                seen.add(sp)
                spans.append(sp)

    for m in _NUM_MY.finditer(text):
        mo, y = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            sp = _span_for_month_year(y, mo)
            if sp not in seen:
                seen.add(sp)
                spans.append(sp)

    return spans


def try_explicit_calendar_month_range(question: str) -> tuple[date, date] | None:
    """
    If the question clearly refers to exactly one calendar month and year, return [first, last] inclusive.
    Returns None when ambiguous (multiple months, comparison language, or no match).
    """
    if not question or not question.strip():
        return None
    if _COMPARE_RE.search(question):
        return None

    spans = _all_month_year_spans(question)
    if len(spans) != 1:
        return None
    return spans[0]


def merge_explicit_calendar_month_into_plan(plan: dict[str, Any], question: str) -> dict[str, Any]:
    """
    When the user already named a calendar month and year (e.g. Mar'26), force a rollup range
    and drop fiscal-year clarification — the LLM sometimes still asks despite the prompt.
    """
    rng = try_explicit_calendar_month_range(question)
    if rng is None:
        return plan

    d0, d1 = rng
    out = dict(plan)
    out["needs_clarification"] = False
    out["clarification_prompts"] = []
    out["intent"] = "rollup"
    out["revenue_date_from"] = d0.isoformat()
    out["revenue_date_to"] = d1.isoformat()
    out["calendar_quarter"] = (d0.month - 1) // 3 + 1
    out["interpretation"] = f"Revenue for calendar {d0.strftime('%B %Y')}"
    if out.get("hierarchy") not in ("org", "bu", "division", "customer"):
        out["hierarchy"] = "org"
    out["compare"] = None
    out["current_period_from"] = None
    out["current_period_to"] = None
    out["comparison_period_from"] = None
    out["comparison_period_to"] = None
    return out
