"""Execute variance_comment NL plans — reads revenue_variance_comment via ORM only (no LLM SQL)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.semantic_layer import load_semantic_bundle
from app.models.dimensions import DimBusinessUnit, DimCustomer, DimDivision
from app.models.phase7 import RevenueVarianceComment
from app.models.tenant import User
from app.services.query_engine.exceptions import QueryUnsafeError

MAX_VARIANCE_COMMENT_ROWS = 150


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _specificity(row: RevenueVarianceComment) -> int:
    if row.division_id is not None:
        return 3
    if row.business_unit_id is not None:
        return 2
    return 1


def _pick_best_comment(rows: list[RevenueVarianceComment]) -> RevenueVarianceComment | None:
    if not rows:
        return None
    return sorted(rows, key=lambda r: (_specificity(r), r.updated_at), reverse=True)[0]


async def execute_variance_comment_plan(
    session: AsyncSession,
    *,
    user: User,
    plan: dict[str, Any],
    org_filter: uuid.UUID | None,
    accessible: set[uuid.UUID],
) -> tuple[list[str], list[dict[str, Any]], str]:
    """Return columns, rows, semantic_version_label."""
    bundle = load_semantic_bundle()
    raw_m = plan.get("variance_revenue_month")
    if not raw_m:
        raise QueryUnsafeError("Missing variance month — include at least one calendar month in your question.")
    try:
        y, mo, d = (int(x) for x in str(raw_m).split("-")[:3])
        vm = date(y, mo, d)
    except (ValueError, TypeError) as e:
        raise QueryUnsafeError("Invalid variance_revenue_month") from e
    month_key = _month_start(vm)

    org_from_plan = _parse_uuid(plan.get("org_id"))
    effective_org = org_filter or org_from_plan
    if effective_org is None:
        raise QueryUnsafeError("Select an organization (or name one the model can resolve).")
    if effective_org not in accessible:
        raise QueryUnsafeError("Organization is not in your access scope")

    cust_id = _parse_uuid(plan.get("customer_id"))
    div_id = _parse_uuid(plan.get("division_id"))
    bu_id = _parse_uuid(plan.get("business_unit_id"))

    stmt: Select[Any]
    bu_tbl = aliased(DimBusinessUnit)
    div_tbl = aliased(DimDivision)

    stmt = (
        select(
            RevenueVarianceComment,
            DimCustomer.customer_name,
            bu_tbl.business_unit_name,
            div_tbl.division_name,
        )
        .join(DimCustomer, DimCustomer.customer_id == RevenueVarianceComment.customer_id)
        .outerjoin(bu_tbl, bu_tbl.business_unit_id == RevenueVarianceComment.business_unit_id)
        .outerjoin(div_tbl, div_tbl.division_id == RevenueVarianceComment.division_id)
        .where(
            RevenueVarianceComment.tenant_id == user.tenant_id,
            RevenueVarianceComment.org_id == effective_org,
            RevenueVarianceComment.revenue_month == month_key,
        )
    )

    if cust_id is not None:
        stmt = stmt.where(RevenueVarianceComment.customer_id == cust_id)
    if div_id is not None:
        stmt = stmt.where(RevenueVarianceComment.division_id == div_id)
    elif bu_id is not None:
        stmt = stmt.where(
            and_(
                RevenueVarianceComment.business_unit_id == bu_id,
                RevenueVarianceComment.division_id.is_(None),
            )
        )

    stmt = stmt.order_by(DimCustomer.customer_name.asc()).limit(MAX_VARIANCE_COMMENT_ROWS + 1)
    res = await session.execute(stmt)
    fetched = res.all()

    if len(fetched) > MAX_VARIANCE_COMMENT_ROWS:
        raise QueryUnsafeError(
            "Too many variance comments for this scope — narrow by customer, division, or BU."
        )

    cols = [
        "customer_name",
        "business_unit_name",
        "division_name",
        "revenue_month",
        "variance_comment",
    ]

    if cust_id is not None:
        if not fetched:
            cname = await session.scalar(
                select(DimCustomer.customer_name).where(
                    DimCustomer.tenant_id == user.tenant_id,
                    DimCustomer.customer_id == cust_id,
                )
            )
            out = [
                {
                    "customer_name": cname or "",
                    "business_unit_name": "",
                    "division_name": "",
                    "revenue_month": month_key.isoformat(),
                    "variance_comment": None,
                }
            ]
            return cols, out, bundle.version_label
        rows_only = [r[0] for r in fetched]
        best = _pick_best_comment(rows_only)
        assert best is not None
        winner_row = next(r for r in fetched if r[0].variance_comment_id == best.variance_comment_id)
        vc, cname, buname, divname = winner_row[0], winner_row[1], winner_row[2], winner_row[3]
        text = (vc.comment_text or "").strip()
        out = [
            {
                "customer_name": cname,
                "business_unit_name": buname or "",
                "division_name": divname or "",
                "revenue_month": month_key.isoformat(),
                "variance_comment": text if text else None,
            }
        ]
        return cols, out, bundle.version_label

    if not fetched:
        empty = [
            {
                "customer_name": "",
                "business_unit_name": "",
                "division_name": "",
                "revenue_month": month_key.isoformat(),
                "variance_comment": None,
            }
        ]
        return cols, empty, bundle.version_label

    out_rows: list[dict[str, Any]] = []
    for vc, cname, buname, divname in fetched:
        text = (vc.comment_text or "").strip()
        out_rows.append(
            {
                "customer_name": cname,
                "business_unit_name": buname or "",
                "division_name": divname or "",
                "revenue_month": month_key.isoformat(),
                "variance_comment": text if text else None,
            }
        )
    return cols, out_rows, bundle.version_label


def _parse_uuid(s: Any) -> uuid.UUID | None:
    if s is None:
        return None
    if isinstance(s, uuid.UUID):
        return s
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError):
        return None
