"""NL orchestration — structured LLM plan, validation, analytics service execution."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.semantic_layer import load_semantic_bundle
from app.models.audit import QueryAuditLog
from app.models.nl_semantic import NlQuerySession, SemanticLayerVersion
from app.models.tenant import User
from app.services.access_scope import accessible_org_ids
from app.services.analytics.service import revenue_compare, revenue_rollup
from app.services.query_engine.exceptions import (
    LlmUnavailableError,
    QueryTimeoutError,
    QueryUnsafeError,
)
from app.core.config import get_settings
from app.services.query_engine.llm import complete_nl_plan

logger = logging.getLogger(__name__)

Hierarchy = Literal["org", "bu", "division"]
CompareKind = Literal["mom", "qoq", "yoy"]

MAX_DATE_SPAN_DAYS = 366 * 10


def _quarter_range(year: int, quarter: int) -> tuple[date, date]:
    bounds = {
        1: ((1, 1), (3, 31)),
        2: ((4, 1), (6, 30)),
        3: ((7, 1), (9, 30)),
        4: ((10, 1), (12, 31)),
    }
    (m1, d1), (m2, d2) = bounds[quarter]
    return date(year, m1, d1), date(year, m2, d2)


def _try_extract_calendar_quarter(plan: dict[str, Any]) -> int | None:
    """Resolve Q1–Q4 from LLM output, or None if nothing in the plan implies a quarter."""
    for key in ("calendar_quarter", "quarter", "fiscal_quarter"):
        raw = plan.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool):
            continue
        if isinstance(raw, (int, float)):
            qi = int(raw)
            if qi in (1, 2, 3, 4):
                return qi
        if isinstance(raw, str):
            s = raw.strip().upper().replace(" ", "")
            if len(s) >= 2 and s[0] == "Q" and s[1:].isdigit():
                qi = int(s[1:])
                if qi in (1, 2, 3, 4):
                    return qi
            if s.isdigit():
                qi = int(s)
                if qi in (1, 2, 3, 4):
                    return qi
    for key in ("revenue_date_from", "revenue_date_to", "current_period_from", "current_period_to"):
        d = _parse_date(plan.get(key))
        if d is not None:
            return (d.month - 1) // 3 + 1
    return None


def _extract_calendar_quarter(plan: dict[str, Any]) -> int:
    qi = _try_extract_calendar_quarter(plan)
    if qi is None:
        raise QueryUnsafeError(
            "Could not resolve quarter after clarification — choose a year again or rephrase with an explicit quarter (e.g. Q3 2026)"
        )
    return qi


def _text_implies_last_or_previous_month(*parts: str | None) -> bool:
    combined = " ".join(p for p in parts if p).lower()
    needles = (
        "last month",
        "previous month",
        "prior month",
        "last month's",
        "month's revenue",
        "month revenue",
    )
    return any(n in combined for n in needles)


def _last_month_range_for_year_choice(year: int, *, anchor: date | None = None) -> tuple[date, date]:
    """
    After fiscal_year disambiguation when the question was about a single calendar month
    but the plan had no quarter: map the chosen year to one concrete month of revenue.
    - Past years: December of that year (last month of that calendar year).
    - Current year: the last completed calendar month (same as colloquial "last month" when asking today).
    - Future years: December of (year - 1) so the window stays in the past.
    """
    today = anchor or date.today()
    if year < today.year:
        return date(year, 12, 1), date(year, 12, 31)
    if year == today.year:
        first_this = date(today.year, today.month, 1)
        end_prev = first_this - timedelta(days=1)
        d0 = date(end_prev.year, end_prev.month, 1)
        return d0, end_prev
    y = year - 1
    return date(y, 12, 1), date(y, 12, 31)


def _parse_date(s: Any) -> date | None:
    if s is None:
        return None
    if isinstance(s, date):
        return s
    if not isinstance(s, str):
        return None
    try:
        y, m, d = (int(x) for x in s.split("-")[:3])
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def _parse_uuid(s: Any) -> uuid.UUID | None:
    if s is None:
        return None
    if isinstance(s, uuid.UUID):
        return s
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError):
        return None


async def _sync_semantic_version(session: AsyncSession, tenant_id: uuid.UUID) -> SemanticLayerVersion:
    bundle = load_semantic_bundle()
    res = await session.execute(
        select(SemanticLayerVersion).where(
            SemanticLayerVersion.tenant_id == tenant_id,
            SemanticLayerVersion.is_active.is_(True),
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = SemanticLayerVersion(
            tenant_id=tenant_id,
            version_label=bundle.version_label,
            source_identifier="semantic_layer.yaml",
            content_sha256=bundle.content_sha256,
            is_active=True,
        )
        session.add(row)
    elif row.content_sha256 != bundle.content_sha256 or row.version_label != bundle.version_label:
        row.version_label = bundle.version_label
        row.source_identifier = "semantic_layer.yaml"
        row.content_sha256 = bundle.content_sha256
        row.effective_from = datetime.now(timezone.utc)
    await session.flush()
    return row


def _validate_date_span(d0: date, d1: date) -> None:
    if d1 < d0:
        raise QueryUnsafeError("Invalid date range")
    if (d1 - d0).days > MAX_DATE_SPAN_DAYS:
        raise QueryUnsafeError("Date range exceeds allowed span")


def _validate_plan(plan: dict[str, Any]) -> None:
    intent = plan.get("intent")
    if intent not in ("rollup", "compare"):
        raise QueryUnsafeError("Unsupported or missing intent")
    h = plan.get("hierarchy")
    if h not in ("org", "bu", "division"):
        raise QueryUnsafeError("Invalid hierarchy")
    if intent == "rollup":
        d0 = _parse_date(plan.get("revenue_date_from"))
        d1 = _parse_date(plan.get("revenue_date_to"))
        if d0 is None or d1 is None:
            raise QueryUnsafeError("Missing date range for rollup")
        _validate_date_span(d0, d1)
    else:
        cf = _parse_date(plan.get("current_period_from"))
        ct = _parse_date(plan.get("current_period_to"))
        bf = _parse_date(plan.get("comparison_period_from"))
        bt = _parse_date(plan.get("comparison_period_to"))
        ckind = plan.get("compare")
        if None in (cf, ct, bf, bt) or ckind not in ("mom", "qoq", "yoy"):
            raise QueryUnsafeError("Incomplete comparison plan")
        _validate_date_span(cf, ct)
        _validate_date_span(bf, bt)


async def _execute_plan(
    session: AsyncSession,
    *,
    user: User,
    plan: dict[str, Any],
    org_filter: uuid.UUID | None,
    accessible: set[uuid.UUID],
) -> tuple[list[str], list[dict[str, Any]], str]:
    """Return columns, rows, semantic_version_label."""
    bundle = load_semantic_bundle()
    intent = plan["intent"]
    hierarchy: Hierarchy = plan["hierarchy"]
    org_from_plan = _parse_uuid(plan.get("org_id"))
    effective_org = org_filter or org_from_plan
    if effective_org is not None and effective_org not in accessible:
        raise QueryUnsafeError("Organization is not in your access scope")

    if intent == "rollup":
        d0 = _parse_date(plan["revenue_date_from"])
        d1 = _parse_date(plan["revenue_date_to"])
        assert d0 is not None and d1 is not None
        payload, _ = await revenue_rollup(
            session,
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            hierarchy=hierarchy,
            revenue_date_from=d0,
            revenue_date_to=d1,
            org_id=effective_org,
            business_unit_id=None,
            division_id=None,
            revenue_type_id=None,
            customer_id=None,
        )
        rows = payload["rows"]
        if hierarchy == "org":
            cols = ["org_name", "total_revenue"]
            out = [{"org_name": r["org_name"], "total_revenue": r["revenue"]} for r in rows]
        elif hierarchy == "bu":
            cols = ["business_unit_name", "total_revenue"]
            out = [
                {"business_unit_name": r["business_unit_name"], "total_revenue": r["revenue"]}
                for r in rows
            ]
        else:
            cols = ["division_name", "total_revenue"]
            out = [
                {"division_name": r["division_name"], "total_revenue": r["revenue"]}
                for r in rows
            ]
        return cols, out, bundle.version_label

    cf = _parse_date(plan["current_period_from"])
    ct = _parse_date(plan["current_period_to"])
    bf = _parse_date(plan["comparison_period_from"])
    bt = _parse_date(plan["comparison_period_to"])
    ck: CompareKind = plan["compare"]
    assert all(x is not None for x in (cf, ct, bf, bt))
    payload, _ = await revenue_compare(
        session,
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        hierarchy=hierarchy,
        compare=ck,
        current_period_from=cf,
        current_period_to=ct,
        comparison_period_from=bf,
        comparison_period_to=bt,
        org_id=effective_org,
        business_unit_id=None,
        division_id=None,
        revenue_type_id=None,
        customer_id=None,
    )
    rows = payload["rows"]
    if hierarchy == "bu":
        cols = [
            "business_unit_name",
            "current_revenue",
            "comparison_revenue",
            "absolute_change",
            "percent_change",
        ]
        out = [
            {
                "business_unit_name": r.get("business_unit_name"),
                "current_revenue": r.get("current_revenue"),
                "comparison_revenue": r.get("comparison_revenue"),
                "absolute_change": r.get("absolute_change"),
                "percent_change": r.get("percent_change"),
            }
            for r in rows
        ]
    elif hierarchy == "org":
        cols = [
            "org_name",
            "current_revenue",
            "comparison_revenue",
            "absolute_change",
            "percent_change",
        ]
        out = [
            {
                "org_name": r.get("org_name"),
                "current_revenue": r.get("current_revenue"),
                "comparison_revenue": r.get("comparison_revenue"),
                "absolute_change": r.get("absolute_change"),
                "percent_change": r.get("percent_change"),
            }
            for r in rows
        ]
    else:
        cols = [
            "division_name",
            "current_revenue",
            "comparison_revenue",
            "absolute_change",
            "percent_change",
        ]
        out = [
            {
                "division_name": r.get("division_name"),
                "current_revenue": r.get("current_revenue"),
                "comparison_revenue": r.get("comparison_revenue"),
                "absolute_change": r.get("absolute_change"),
                "percent_change": r.get("percent_change"),
            }
            for r in rows
        ]
    return cols, out, bundle.version_label


def _merge_year_into_plan(
    plan: dict[str, Any],
    year: int,
    *,
    original_question: str | None = None,
    _date_anchor: date | None = None,
) -> dict[str, Any]:
    """Apply fiscal_year clarification: quarter+year, or single-month rollup when quarter was never set."""
    qi = _try_extract_calendar_quarter(plan)
    out = {**plan}
    out["needs_clarification"] = False
    combined_hint = " ".join(
        filter(
            None,
            [
                original_question or "",
                str(out.get("interpretation") or ""),
            ],
        )
    )
    if qi is not None:
        d0, d1 = _quarter_range(year, qi)
        if out.get("intent") == "rollup":
            out["revenue_date_from"] = d0.isoformat()
            out["revenue_date_to"] = d1.isoformat()
        else:
            if out.get("compare") == "yoy":
                out["current_period_from"] = d0.isoformat()
                out["current_period_to"] = d1.isoformat()
                p0 = date(year - 1, d0.month, d0.day)
                p1 = date(year - 1, d1.month, d1.day)
                out["comparison_period_from"] = p0.isoformat()
                out["comparison_period_to"] = p1.isoformat()
            else:
                raise QueryUnsafeError("Unsupported comparison after clarification")
        return out

    if (
        out.get("intent") == "rollup"
        and _text_implies_last_or_previous_month(combined_hint)
    ):
        d0, d1 = _last_month_range_for_year_choice(year, anchor=_date_anchor)
        out["revenue_date_from"] = d0.isoformat()
        out["revenue_date_to"] = d1.isoformat()
        return out

    raise QueryUnsafeError(
        "Could not resolve quarter after clarification — choose a year again or rephrase with an explicit quarter (e.g. Q3 2026)"
    )


def _apply_clarifications(
    pending: dict[str, Any], clarifications: list[dict[str, Any]] | None
) -> dict[str, Any]:
    plan = pending.get("plan")
    if not isinstance(plan, dict):
        raise QueryUnsafeError("Invalid session state")
    if not clarifications:
        raise QueryUnsafeError("Missing clarifications")
    merged = dict(plan)
    for c in clarifications:
        pid = c.get("prompt_id")
        choice = c.get("choice")
        if pid == "fiscal_year" and choice is not None:
            try:
                year = int(str(choice))
            except ValueError as e:
                raise QueryUnsafeError("Invalid year choice") from e
            merged = _merge_year_into_plan(
                merged, year, original_question=str(pending.get("question") or "")
            )
            return merged
    raise QueryUnsafeError("Unknown clarification")


async def run_natural_language_query(
    session: AsyncSession,
    *,
    user: User,
    question: str,
    org_id: uuid.UUID | None,
    disambiguation_token: str | None,
    clarifications: list[dict[str, Any]] | None,
    correlation_id: uuid.UUID | None,
) -> dict[str, Any]:
    """
    Returns a dict matching POST /query/natural-language contract (status completed or needs_clarification).
    Raises QueryUnsafeError, QueryTimeoutError, LlmUnavailableError for router mapping.
    """
    deadline = get_settings().QUERY_TIMEOUT_SECONDS
    semantic_row = await _sync_semantic_version(session, user.tenant_id)
    accessible = await accessible_org_ids(session, user.user_id)

    async def _with_timeout(coro: Any) -> Any:
        try:
            return await asyncio.wait_for(coro, timeout=deadline)
        except TimeoutError as e:
            raise QueryTimeoutError("Query processing timed out") from e

    plan: dict[str, Any]
    nl_session: NlQuerySession | None = None
    token_plain: str | None = None
    audit_question = question

    if disambiguation_token and clarifications is not None:
        th = hashlib.sha256(disambiguation_token.encode()).hexdigest()
        res = await session.execute(
            select(NlQuerySession).where(
                NlQuerySession.tenant_id == user.tenant_id,
                NlQuerySession.user_id == user.user_id,
                NlQuerySession.token_hash == th,
                NlQuerySession.status == "pending_clarification",
            )
        )
        nl_session = res.scalar_one_or_none()
        if nl_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Clarification session expired or invalid",
                        "details": None,
                    }
                },
            )
        if nl_session.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Clarification session expired",
                        "details": None,
                    }
                },
            )
        pending = nl_session.pending_context or {}
        audit_question = str(pending.get("question", question))
        plan = _apply_clarifications(pending, clarifications)
        _validate_plan(plan)
    else:
        try:
            raw_plan = await _with_timeout(complete_nl_plan(question))
        except LlmUnavailableError:
            raise
        plan = raw_plan if isinstance(raw_plan, dict) else {}
        if plan.get("needs_clarification"):
            prompts = plan.get("clarification_prompts") or []
            if not prompts:
                raise QueryUnsafeError("Clarification required but no prompts were provided")
            token_plain = secrets.token_urlsafe(32)
            th = hashlib.sha256(token_plain.encode()).hexdigest()
            expires = datetime.now(timezone.utc) + timedelta(minutes=45)
            nl_session = NlQuerySession(
                tenant_id=user.tenant_id,
                user_id=user.user_id,
                status="pending_clarification",
                pending_context={"question": question, "plan": plan},
                token_hash=th,
                expires_at=expires,
            )
            session.add(nl_session)
            await session.flush()
            log = QueryAuditLog(
                tenant_id=user.tenant_id,
                user_id=user.user_id,
                correlation_id=correlation_id,
                nl_session_id=nl_session.nl_session_id,
                semantic_version_id=semantic_row.version_id,
                natural_query=question,
                resolved_plan=plan,
                execution_ms=None,
                row_count=None,
                status="needs_clarification",
                error_message=None,
            )
            session.add(log)
            await session.flush()
            questions = []
            for p in prompts:
                if not isinstance(p, dict):
                    continue
                questions.append(
                    {
                        "prompt_id": p.get("prompt_id"),
                        "text": p.get("text", ""),
                        "choices": p.get("choices") or [],
                    }
                )
            return {
                "query_id": str(log.log_id),
                "status": "needs_clarification",
                "questions": questions,
                "disambiguation": {"token": token_plain},
                "semantic_version_label": load_semantic_bundle().version_label,
            }
        _validate_plan(plan)

    t0 = time.perf_counter()
    try:
        cols, rows, ver_label = await _with_timeout(
            _execute_plan(session, user=user, plan=plan, org_filter=org_id, accessible=accessible)
        )
    except QueryUnsafeError:
        raise
    ms = int((time.perf_counter() - t0) * 1000)

    fingerprint_src = json.dumps(plan, sort_keys=True, default=str)
    fp = hashlib.sha256(fingerprint_src.encode()).hexdigest()

    resolved = {
        "kind": "structured_summary",
        "metric_keys": ["total_revenue"] if plan.get("intent") == "rollup" else ["compare_revenue"],
        "dimensions": [plan.get("hierarchy")],
        "safe_sql_fingerprint": f"sha256:{fp}",
        "intent": plan.get("intent"),
    }

    log = QueryAuditLog(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        correlation_id=correlation_id,
        nl_session_id=nl_session.nl_session_id if nl_session else None,
        semantic_version_id=semantic_row.version_id,
        natural_query=audit_question,
        resolved_plan=resolved,
        execution_ms=ms,
        row_count=len(rows),
        status="success",
        error_message=None,
    )
    session.add(log)
    if nl_session:
        nl_session.status = "completed"
        nl_session.updated_at = datetime.now(timezone.utc)
    await session.flush()

    return {
        "query_id": str(log.log_id),
        "status": "completed",
        "interpretation": plan.get("interpretation") or "Resolved revenue query",
        "columns": cols,
        "rows": rows,
        "disambiguation": None,
        "semantic_version_label": ver_label,
    }
