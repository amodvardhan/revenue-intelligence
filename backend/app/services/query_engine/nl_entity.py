"""Resolve customer / organization / business unit names from NL questions — parameterized DB lookups only."""

from __future__ import annotations

import re
import uuid
from difflib import SequenceMatcher
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimBusinessUnit, DimCustomer, DimDivision, DimOrganization
from app.models.tenant import User
from app.services.access_scope import business_unit_scope
from app.services.query_engine.exceptions import QueryUnsafeError
from app.services.query_engine.nl_calendar import strip_inline_calendar_expressions

EntityKind = Literal["customer", "org"]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _acronym_from_words(name: str) -> str:
    parts = re.findall(r"[A-Za-z]+", name)
    return "".join(p[0].upper() for p in parts if p)


def _score(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    r0 = SequenceMatcher(None, na, nb).ratio()
    na2 = re.sub(r"[^a-z0-9\s]", "", na)
    nb2 = re.sub(r"[^a-z0-9\s]", "", nb)
    r1 = SequenceMatcher(None, na2, nb2).ratio() if na2 and nb2 else 0.0
    base = max(r0, r1)
    # Acronym match: "WHO" ↔ "World Health Organization"
    if len(na) <= 12 and na.isalpha():
        ax = _acronym_from_words(nb)
        if len(ax) >= 2 and na.upper() == ax:
            return max(base, 0.92)
    return base


_NOT_ENTITY_PHRASE = re.compile(
    r"^(the\s+)?((last|next|this|previous)\s+)?(month|quarter|year|week|half)\b",
    re.IGNORECASE,
)


def _strip_bu_qualifier(phrase: str) -> str:
    s = phrase.strip().rstrip("?.!")
    s = re.sub(r"^(the\s+)?(bu|business\s+unit)\s+", "", s, flags=re.IGNORECASE)
    return s.strip()


def normalize_entity_resolution_phrase(phrase: str) -> str:
    """
    Strip trailing scope qualifiers so "Acme overall this fiscal year" matches dim_organization
    and dim_business_unit names ("Acme") reliably.
    """
    s = phrase.strip().rstrip("?.!").strip()
    # Apply repeatedly — e.g. "... overall in this fiscal year"
    for _ in range(8):
        prev = s
        s = re.sub(
            r"(?i)(?:\s+|\s*,\s*)(overall|in\s+total|company-?wide|enterprise-?wide|consolidated)\s*$",
            "",
            s,
        ).strip()
        s = re.sub(
            r"(?i)(?:\s+|\s*,\s*)(this|in\s+this|for\s+this)\s+(fiscal|financial)\s+year\s*$",
            "",
            s,
        ).strip()
        s = re.sub(r"(?i)(?:\s+|\s*,\s*)(for\s+)?fy\s*\d{2,4}\s*$", "", s).strip()
        s = re.sub(r"(?i)(?:\s+|\s*,\s*)for\s+the\s+(current\s+)?(fiscal|financial)\s+year\s*$", "", s).strip()
        s = s.rstrip("?.!").strip()
        if s == prev:
            break
    return s


async def _fallback_org_or_customer_when_bu_misses(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    accessible_org_ids: set[uuid.UUID],
    plan: dict[str, Any],
    bu_match_phrase: str,
    interpretation_lead: str,
) -> dict[str, Any] | None:
    """
    LLMs often put **organization** names in business_unit_name. If BU fuzzy match fails,
    try customer / organization resolution on the same phrase before erroring.
    """
    cleaned = normalize_entity_resolution_phrase(bu_match_phrase)
    if len(cleaned) < 2:
        return None
    ent = await resolve_entity_for_nl(
        session,
        tenant_id=tenant_id,
        accessible_org_ids=accessible_org_ids,
        phrase=cleaned,
    )
    if ent is None:
        return None
    kind, eid, label = ent
    out = dict(plan)
    out.pop("customer_name", None)
    out.pop("business_unit_name", None)
    out.pop("division_name", None)
    out.pop("business_unit_id", None)
    out.pop("division_id", None)
    if kind == "customer":
        out["hierarchy"] = "customer"
        out["customer_id"] = str(eid)
        out["org_id"] = None
    else:
        out["hierarchy"] = "org"
        out["org_id"] = str(eid)
        out.pop("customer_id", None)
    base = (out.get("interpretation") or "").strip()
    suffix = f"{label} ({'customer' if kind == 'customer' else 'organization'})"
    out["interpretation"] = f"{base} — {suffix}" if base else f"{interpretation_lead} — {suffix}"
    return out


def extract_division_focus_phrase(question: str) -> str | None:
    """Capture a division name from questions mentioning 'division …'."""
    q = strip_inline_calendar_expressions(question)
    if not q:
        return None
    patterns = [
        r"(?i)\b(?:for|in)\s+division\s+([^?.!\n]+)",
        r"(?i)\bdivision\s+([A-Za-z0-9][^?.!\n]{0,160})",
    ]
    for p in patterns:
        m = re.search(p, q, re.IGNORECASE)
        if m:
            phrase = m.group(1).strip().rstrip("?.!")
            phrase = re.sub(r"\s+\b(from|to|for|in|between)\s*$", "", phrase, flags=re.IGNORECASE).strip()
            if len(phrase) < 2 or _NOT_ENTITY_PHRASE.match(phrase.strip()):
                return None
            return phrase
    return None


def extract_business_unit_focus_phrase(question: str) -> str | None:
    """
    Capture a BU name from questions like "growth of the BU Acme" (after calendar stripping).
    """
    q = strip_inline_calendar_expressions(question)
    if not q:
        return None
    patterns = [
        r"(?i)\b(?:overall\s+)?growth\s+of\s+(?:the\s+)?(?:bu|business\s+unit)\s+(.+?)\s*$",
        r"(?i)\brevenue\s+(?:for|from)\s+(?:the\s+)?(?:bu|business\s+unit)\s+(.+?)\s*$",
        r"(?i)\bfor\s+(?:the\s+)?(?:bu|business\s+unit)\s+(.+?)\s*$",
    ]
    for p in patterns:
        m = re.search(p, q, re.IGNORECASE | re.DOTALL)
        if m:
            phrase = m.group(1).strip().rstrip("?.!")
            if len(phrase) < 2 or _NOT_ENTITY_PHRASE.match(phrase.strip()):
                return None
            return _strip_bu_qualifier(phrase)
    return None


def extract_entity_focus_phrase(question: str) -> str | None:
    """
    Best-effort extraction of a customer / org name from natural language.
    Runs after stripping inline calendar hints (Mar'26, etc.).
    """
    q = strip_inline_calendar_expressions(question)
    if not q:
        return None

    patterns = [
        r"\brevenue\b.*\bfor\s+(?:the\s+)?(.+?)\s*$",
        r"\brevenue\b\s+of\s+(?:the\s+)?(.+?)\s*$",
        r"\bsales\b.*\bfor\s+(?:the\s+)?(.+?)\s*$",
        r"\btotal\b.*\bfor\s+(?:the\s+)?(.+?)\s*$",
        r"\bfor\s+(?:the\s+)?(?:customer|client|account)\s+(.+?)\s*$",
    ]
    for p in patterns:
        m = re.search(p, q, re.IGNORECASE | re.DOTALL)
        if m:
            phrase = m.group(1).strip().rstrip("?.!")
            # After removing month/year, a dangling "in" often linked the entity to the date (e.g. "WHO in Mar'26").
            phrase = re.sub(r"\s+\bin\s*$", "", phrase, flags=re.IGNORECASE).strip()
            if len(phrase) < 2 or _NOT_ENTITY_PHRASE.match(phrase.strip()):
                return None
            trimmed = normalize_entity_resolution_phrase(phrase)
            return trimmed if trimmed else phrase
    return None


async def _load_customers(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[tuple[uuid.UUID, str]]:
    res = await session.execute(
        select(DimCustomer.customer_id, DimCustomer.customer_name, DimCustomer.customer_name_common).where(
            DimCustomer.tenant_id == tenant_id,
            DimCustomer.is_active.is_(True),
        )
    )
    out: list[tuple[uuid.UUID, str]] = []
    for cid, cname, ccommon in res.all():
        out.append((cid, cname))
        if (ccommon or "").strip():
            out.append((cid, f"{cname} ({ccommon})"))
    return out


async def _load_business_units_for_nl(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    accessible: set[uuid.UUID],
    org_id_hint: uuid.UUID | None,
) -> list[tuple[uuid.UUID, uuid.UUID, str]]:
    """(business_unit_id, org_id, business_unit_name), scoped by org access and optional BU restrictions."""
    if not accessible:
        return []
    mode, allowed_bu_ids = await business_unit_scope(session, user_id)
    stmt = select(
        DimBusinessUnit.business_unit_id,
        DimBusinessUnit.org_id,
        DimBusinessUnit.business_unit_name,
    ).where(
        DimBusinessUnit.tenant_id == tenant_id,
        DimBusinessUnit.org_id.in_(accessible),
        DimBusinessUnit.is_active.is_(True),
    )
    if org_id_hint is not None:
        stmt = stmt.where(DimBusinessUnit.org_id == org_id_hint)
    res = await session.execute(stmt)
    rows = [(r[0], r[1], r[2]) for r in res.all()]
    if mode == "restricted":
        allow = set(allowed_bu_ids)
        rows = [t for t in rows if t[0] in allow]
    return rows


async def _load_divisions_for_nl(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    accessible_org_ids: set[uuid.UUID],
    org_id_hint: uuid.UUID | None,
    business_unit_id_hint: uuid.UUID | None,
) -> list[tuple[uuid.UUID, uuid.UUID, uuid.UUID, str]]:
    """Rows: (division_id, business_unit_id, org_id, division_name)."""
    if not accessible_org_ids:
        return []
    stmt = (
        select(
            DimDivision.division_id,
            DimDivision.business_unit_id,
            DimBusinessUnit.org_id,
            DimDivision.division_name,
        )
        .join(DimBusinessUnit, DimBusinessUnit.business_unit_id == DimDivision.business_unit_id)
        .where(
            DimDivision.tenant_id == tenant_id,
            DimBusinessUnit.tenant_id == tenant_id,
            DimDivision.is_active.is_(True),
            DimBusinessUnit.is_active.is_(True),
            DimBusinessUnit.org_id.in_(accessible_org_ids),
        )
    )
    if org_id_hint is not None:
        stmt = stmt.where(DimBusinessUnit.org_id == org_id_hint)
    if business_unit_id_hint is not None:
        stmt = stmt.where(DimDivision.business_unit_id == business_unit_id_hint)
    res = await session.execute(stmt)
    return [(r[0], r[1], r[2], r[3]) for r in res.all()]


async def resolve_division_for_nl(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    accessible_org_ids: set[uuid.UUID],
    org_id_hint: uuid.UUID | None,
    business_unit_id_hint: uuid.UUID | None,
    phrase: str,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str] | None:
    """Match phrase to a single division (fuzzy), or None."""
    rows = await _load_divisions_for_nl(
        session,
        tenant_id=tenant_id,
        accessible_org_ids=accessible_org_ids,
        org_id_hint=org_id_hint,
        business_unit_id_hint=business_unit_id_hint,
    )
    flat: list[tuple[uuid.UUID, str]] = [(rid, name) for rid, _bu, _oid, name in rows]
    hit = _pick_best(phrase, flat)
    if hit is None:
        return None
    div_id, _label, _score = hit
    for r_div, r_bu, r_oid, r_name in rows:
        if r_div == div_id:
            return (r_div, r_bu, r_oid, r_name)
    return None


async def resolve_business_unit_for_nl(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    accessible_org_ids: set[uuid.UUID],
    org_id_hint: uuid.UUID | None,
    phrase: str,
) -> tuple[uuid.UUID, uuid.UUID, str] | None:
    """Match phrase to a single BU (fuzzy), or None."""
    rows = await _load_business_units_for_nl(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        accessible=accessible_org_ids,
        org_id_hint=org_id_hint,
    )
    flat: list[tuple[uuid.UUID, str]] = [(bid, name) for bid, _oid, name in rows]
    hit = _pick_best(phrase, flat)
    if hit is None:
        return None
    bid, _label, _score = hit
    for r_bid, r_oid, r_name in rows:
        if r_bid == bid:
            return (r_bid, r_oid, r_name)
    return None


async def _load_orgs(
    session: AsyncSession, tenant_id: uuid.UUID, accessible: set[uuid.UUID]
) -> list[tuple[uuid.UUID, str]]:
    if not accessible:
        return []
    res = await session.execute(
        select(DimOrganization.org_id, DimOrganization.org_name).where(
            DimOrganization.tenant_id == tenant_id,
            DimOrganization.org_id.in_(accessible),
            DimOrganization.is_active.is_(True),
        )
    )
    return [(r[0], r[1]) for r in res.all()]


def _pick_best(
    phrase: str, rows: list[tuple[uuid.UUID, str]]
) -> tuple[uuid.UUID, str, float] | None:
    if not rows:
        return None
    by_id: dict[uuid.UUID, tuple[str, float]] = {}
    for oid, label in rows:
        sc = _score(phrase, label)
        prev = by_id.get(oid)
        if prev is None or sc > prev[1]:
            by_id[oid] = (label, sc)
    scored = [(oid, lab, sc) for oid, (lab, sc) in by_id.items()]
    scored.sort(key=lambda x: -x[2])
    best = scored[0]
    if best[2] < 0.58:
        return None
    if len(scored) > 1:
        second = scored[1]
        if second[2] >= 0.58 and (best[2] - second[2]) < 0.06 and best[0] != second[0]:
            return None
    return best[0], best[1], best[2]


async def resolve_entity_for_nl(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    accessible_org_ids: set[uuid.UUID],
    phrase: str,
) -> tuple[EntityKind, uuid.UUID, str] | None:
    """
    Match phrase to a single customer or organization (fuzzy), or return None.
    Customer matches take precedence when scores are close.
    """
    cust_rows = await _load_customers(session, tenant_id)
    org_rows = await _load_orgs(session, tenant_id, accessible_org_ids)

    c_best = _pick_best(phrase, cust_rows)
    o_best = _pick_best(phrase, org_rows)

    if c_best and o_best:
        if c_best[2] >= o_best[2] + 0.04:
            return ("customer", c_best[0], c_best[1])
        if o_best[2] >= c_best[2] + 0.04:
            return ("org", o_best[0], o_best[1])
        if c_best[2] >= o_best[2]:
            return ("customer", c_best[0], c_best[1])
        return ("org", o_best[0], o_best[1])

    if c_best:
        return ("customer", c_best[0], c_best[1])
    if o_best:
        return ("org", o_best[0], o_best[1])
    return None


async def merge_resolved_entity_into_plan(
    session: AsyncSession,
    user: User,
    question: str,
    plan: dict[str, Any],
    *,
    accessible_org_ids: set[uuid.UUID],
    org_id_hint: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    When the user names a customer, org, or business unit (or the LLM sets names), resolve
    against dimensions and narrow the plan. If a phrase is present but nothing matches, fail closed
    (do not run an unscoped rollup).
    """
    phrase_bu_name = (plan.get("business_unit_name") or "").strip()
    raw_cust = (plan.get("customer_name") or "").strip()
    hierarchy = plan.get("hierarchy")

    bu_match_phrase = phrase_bu_name
    if not bu_match_phrase and hierarchy == "bu":
        bu_match_phrase = _strip_bu_qualifier(raw_cust) if raw_cust else ""
    if not bu_match_phrase:
        ex = extract_business_unit_focus_phrase(question)
        if ex:
            bu_match_phrase = _strip_bu_qualifier(ex)
    if not bu_match_phrase and hierarchy == "bu":
        ex2 = extract_entity_focus_phrase(question)
        if ex2:
            bu_match_phrase = _strip_bu_qualifier(ex2)

    bu_hint_from_wording = extract_business_unit_focus_phrase(question) is not None
    should_attempt_bu = bool(phrase_bu_name) or hierarchy == "bu" or bu_hint_from_wording

    if should_attempt_bu and bu_match_phrase:
        qbu = normalize_entity_resolution_phrase(bu_match_phrase) or bu_match_phrase.strip()
        bu_hit = await resolve_business_unit_for_nl(
            session,
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            accessible_org_ids=accessible_org_ids,
            org_id_hint=org_id_hint,
            phrase=qbu,
        )
        if bu_hit:
            bu_id, org_id, label = bu_hit
            out = dict(plan)
            out.pop("customer_name", None)
            out.pop("business_unit_name", None)
            out["hierarchy"] = "bu"
            out["business_unit_id"] = str(bu_id)
            out["org_id"] = str(org_id)
            base = (out.get("interpretation") or "").strip()
            suffix = f"{label} (business unit)"
            out["interpretation"] = f"{base} — {suffix}" if base else f"Revenue — {suffix}"
            return out
        if phrase_bu_name or hierarchy == "bu" or bu_hint_from_wording:
            fb = await _fallback_org_or_customer_when_bu_misses(
                session,
                tenant_id=user.tenant_id,
                accessible_org_ids=accessible_org_ids,
                plan=plan,
                bu_match_phrase=bu_match_phrase,
                interpretation_lead="Revenue",
            )
            if fb is not None:
                return fb
            raise QueryUnsafeError(
                f'No business unit, organization, or customer in your data closely matches "{qbu}". '
                "Check spelling, import coverage, or pick Organization (optional) above."
            )

    if hierarchy == "bu" and not bu_match_phrase:
        return plan

    raw_name = raw_cust
    phrase = raw_name or extract_entity_focus_phrase(question)
    if not phrase:
        return plan

    ent = await resolve_entity_for_nl(
        session,
        tenant_id=user.tenant_id,
        accessible_org_ids=accessible_org_ids,
        phrase=phrase,
    )
    if ent is None:
        raise QueryUnsafeError(
            f'No customer or organization in your data closely matches "{phrase}". '
            "Check spelling, import coverage, or pick Organization (optional) above."
        )

    kind, eid, label = ent
    out = dict(plan)
    out.pop("customer_name", None)
    out.pop("business_unit_name", None)
    if kind == "customer":
        out["hierarchy"] = "customer"
        out["customer_id"] = str(eid)
        out["org_id"] = None
    else:
        out["hierarchy"] = "org"
        out["org_id"] = str(eid)
        out.pop("customer_id", None)

    base = (out.get("interpretation") or "").strip()
    suffix = f"{label} ({'customer' if kind == 'customer' else 'organization'})"
    out["interpretation"] = f"{base} — {suffix}" if base else f"Revenue — {suffix}"
    return out


async def merge_variance_entities_into_plan(
    session: AsyncSession,
    user: User,
    question: str,
    plan: dict[str, Any],
    *,
    accessible_org_ids: set[uuid.UUID],
    org_id_hint: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Resolve BU / division / customer for intent variance_comment — parameterized lookups only.
    """
    phrase_bu_name = (plan.get("business_unit_name") or "").strip()
    raw_cust = (plan.get("customer_name") or "").strip()
    phrase_div = (plan.get("division_name") or "").strip()
    hierarchy = plan.get("hierarchy")

    bu_match_phrase = phrase_bu_name
    if not bu_match_phrase and hierarchy == "bu":
        bu_match_phrase = _strip_bu_qualifier(raw_cust) if raw_cust else ""
    if not bu_match_phrase:
        ex = extract_business_unit_focus_phrase(question)
        if ex:
            bu_match_phrase = _strip_bu_qualifier(ex)
    if not bu_match_phrase and hierarchy == "bu":
        ex2 = extract_entity_focus_phrase(question)
        if ex2:
            bu_match_phrase = _strip_bu_qualifier(ex2)

    bu_hint_from_wording = extract_business_unit_focus_phrase(question) is not None
    should_attempt_bu = bool(phrase_bu_name) or hierarchy == "bu" or bu_hint_from_wording

    bu_id_hint: uuid.UUID | None = None
    if should_attempt_bu and bu_match_phrase:
        qbu = normalize_entity_resolution_phrase(bu_match_phrase) or bu_match_phrase.strip()
        bu_hit = await resolve_business_unit_for_nl(
            session,
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            accessible_org_ids=accessible_org_ids,
            org_id_hint=org_id_hint,
            phrase=qbu,
        )
        if bu_hit:
            bu_id_hint = bu_hit[0]
            bid, org_id, label = bu_hit
            out = dict(plan)
            out.pop("customer_name", None)
            out.pop("business_unit_name", None)
            out.pop("division_name", None)
            out["hierarchy"] = "bu"
            out["business_unit_id"] = str(bid)
            out["org_id"] = str(org_id)
            base = (out.get("interpretation") or "").strip()
            suffix = f"{label} (business unit)"
            out["interpretation"] = f"{base} — {suffix}" if base else f"Variance narrative — {suffix}"
            plan = out
        elif phrase_bu_name or hierarchy == "bu" or bu_hint_from_wording:
            fb = await _fallback_org_or_customer_when_bu_misses(
                session,
                tenant_id=user.tenant_id,
                accessible_org_ids=accessible_org_ids,
                plan=plan,
                bu_match_phrase=bu_match_phrase,
                interpretation_lead="Variance narrative",
            )
            if fb is not None:
                plan = fb
            else:
                raise QueryUnsafeError(
                    f'No business unit, organization, or customer in your data closely matches "{qbu}". '
                    "Check spelling or narrow Organization above."
                )

    pdiv = phrase_div.strip() or (extract_division_focus_phrase(question) or "").strip()
    div_wanted = bool(pdiv) or hierarchy == "division"

    div_bu_filter = bu_id_hint
    parsed_bu = _parse_uuid(plan.get("business_unit_id"))
    if div_bu_filter is None and parsed_bu is not None:
        div_bu_filter = parsed_bu

    if hierarchy == "division" and not pdiv:
        raise QueryUnsafeError(
            "Could not determine which division — include the division name in your question."
        )

    if div_wanted and pdiv:
        div_hit = await resolve_division_for_nl(
            session,
            tenant_id=user.tenant_id,
            accessible_org_ids=accessible_org_ids,
            org_id_hint=org_id_hint,
            business_unit_id_hint=div_bu_filter,
            phrase=pdiv,
        )
        if div_hit:
            div_id, bu_id, org_id, label = div_hit
            out = dict(plan)
            out.pop("division_name", None)
            out.pop("customer_name", None)
            out["hierarchy"] = "division"
            out["division_id"] = str(div_id)
            out["business_unit_id"] = str(bu_id)
            out["org_id"] = str(org_id)
            base = (out.get("interpretation") or "").strip()
            suffix = f"{label} (division)"
            out["interpretation"] = f"{base} — {suffix}" if base else f"Variance narrative — {suffix}"
            plan = out
        else:
            raise QueryUnsafeError(
                f'No division in your data closely matches "{pdiv}". '
                "Check spelling or narrow Organization / BU above."
            )

    raw_name = raw_cust
    phrase = raw_name or extract_entity_focus_phrase(question)
    want_customer = bool(raw_name.strip()) or hierarchy == "customer"

    if hierarchy == "customer" and not (phrase or "").strip():
        raise QueryUnsafeError(
            "Could not determine which customer — include the customer name in your question."
        )

    if want_customer and phrase:
        ent = await resolve_entity_for_nl(
            session,
            tenant_id=user.tenant_id,
            accessible_org_ids=accessible_org_ids,
            phrase=phrase,
        )
        if ent is None:
            raise QueryUnsafeError(
                f'No customer or organization in your data closely matches "{phrase}". '
                "Check spelling or pick Organization above."
            )
        kind, eid, label = ent
        out = dict(plan)
        out.pop("customer_name", None)
        out.pop("business_unit_name", None)
        if kind == "customer":
            out["hierarchy"] = "customer"
            out["customer_id"] = str(eid)
        elif not out.get("division_id") and not out.get("business_unit_id"):
            out["hierarchy"] = "org"
            out["org_id"] = str(eid)
            out.pop("customer_id", None)
        base = (out.get("interpretation") or "").strip()
        suffix = f"{label} ({'customer' if kind == 'customer' else 'organization'})"
        out["interpretation"] = f"{base} — {suffix}" if base else f"Variance narrative — {suffix}"
        plan = out

    return plan


def _parse_uuid(s: Any) -> uuid.UUID | None:
    if s is None:
        return None
    if isinstance(s, uuid.UUID):
        return s
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError):
        return None
