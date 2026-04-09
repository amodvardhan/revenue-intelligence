"""DM-facing prompts and helpers for revenue variance narratives (matrix MoM / YoY context)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimCustomer
from app.models.facts import FactRevenue
from app.models.phase7 import RevenueManualCell, RevenueVarianceComment
from app.models.tenant import User
from app.schemas.revenue import VarianceCommentPromptItem


VARIANCE_COMMENT_MAX_LEN = 4000

# How far back to scan months for open narrative prompts (facts + manual overrides).
PROMPT_HISTORY_MONTH_SPAN = 24


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _month_add(d: date, delta_months: int) -> date:
    m0 = d.month - 1 + delta_months
    y = d.year + m0 // 12
    m = m0 % 12 + 1
    return date(y, m, 1)


def _amount_str(d: Decimal) -> str:
    return format(d, "f")


async def _customer_org_wide_month_totals(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    org_id: UUID,
    customer_id: UUID,
) -> tuple[dict[date, Decimal], str]:
    """Month → total for org-wide scope; currency from facts."""
    month_bucket = cast(func.date_trunc("month", FactRevenue.revenue_date), Date)
    stmt = (
        select(month_bucket.label("month_key"), func.sum(FactRevenue.amount).label("amt"), func.min(FactRevenue.currency_code))
        .where(
            FactRevenue.tenant_id == tenant_id,
            FactRevenue.org_id == org_id,
            FactRevenue.customer_id == customer_id,
            FactRevenue.is_deleted.is_(False),
        )
        .group_by(month_bucket)
    )
    res = await session.execute(stmt)
    raw = res.all()
    totals: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    ccy = "USD"
    for mkey, amt, c in raw:
        mk = mkey if isinstance(mkey, date) else date.fromisoformat(str(mkey))
        mk = _month_start(mk)
        totals[mk] += amt or Decimal("0")
        if c:
            ccy = c

    mres = await session.execute(
        select(RevenueManualCell).where(
            RevenueManualCell.tenant_id == tenant_id,
            RevenueManualCell.org_id == org_id,
            RevenueManualCell.customer_id == customer_id,
            RevenueManualCell.business_unit_id.is_(None),
            RevenueManualCell.division_id.is_(None),
        )
    )
    for row in mres.scalars().all():
        mk = _month_start(row.revenue_month)
        totals[mk] = Decimal(row.amount)

    return dict(totals), ccy


async def existing_variance_comment_keys(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    org_id: UUID,
    customer_ids: list[UUID],
) -> set[tuple[UUID, date]]:
    """Set of (customer_id, revenue_month month-start) with org-wide comments."""
    if not customer_ids:
        return set()
    res = await session.execute(
        select(RevenueVarianceComment.customer_id, RevenueVarianceComment.revenue_month).where(
            RevenueVarianceComment.tenant_id == tenant_id,
            RevenueVarianceComment.org_id == org_id,
            RevenueVarianceComment.customer_id.in_(customer_ids),
            RevenueVarianceComment.business_unit_id.is_(None),
            RevenueVarianceComment.division_id.is_(None),
        )
    )
    return {(cid, _month_start(rm)) for cid, rm in res.all()}


async def list_dm_variance_prompts(
    session: AsyncSession,
    *,
    user: User,
    org_id: UUID,
    dm_customer_ids: set[UUID],
) -> list[VarianceCommentPromptItem]:
    """Customers with material MoM or YoY movement and no org-wide narrative yet."""
    if not dm_customer_ids:
        return []

    labels: dict[UUID, str] = {}
    cres = await session.execute(
        select(DimCustomer.customer_id, DimCustomer.customer_name).where(
            DimCustomer.tenant_id == user.tenant_id,
            DimCustomer.org_id == org_id,
            DimCustomer.customer_id.in_(dm_customer_ids),
        )
    )
    for cid, name in cres.all():
        labels[cid] = name

    commented = await existing_variance_comment_keys(
        session,
        tenant_id=user.tenant_id,
        org_id=org_id,
        customer_ids=list(dm_customer_ids),
    )

    items: list[VarianceCommentPromptItem] = []
    today = date.today()
    horizon_start = _month_add(_month_start(today), -PROMPT_HISTORY_MONTH_SPAN)

    for cid in sorted(dm_customer_ids, key=lambda x: (labels.get(x, "").lower())):
        totals, ccy = await _customer_org_wide_month_totals(
            session, tenant_id=user.tenant_id, org_id=org_id, customer_id=cid
        )
        if not totals:
            continue
        months_sorted = sorted(totals.keys())
        for j, m in enumerate(months_sorted):
            if m < horizon_start:
                continue
            prev_m = months_sorted[j - 1] if j > 0 else None
            mom: Decimal | None = None
            if prev_m is not None:
                mom = totals[m] - totals[prev_m]

            prior_y = _month_add(m, -12)
            yoy: Decimal | None = None
            if prior_y in totals:
                yoy = totals[m] - totals[prior_y]

            material = (mom is not None and mom != 0) or (yoy is not None and yoy != 0)
            if not material:
                continue
            if (cid, m) in commented:
                continue

            items.append(
                VarianceCommentPromptItem(
                    customer_id=cid,
                    customer_legal=labels.get(cid, ""),
                    revenue_month=m,
                    month_label=m.strftime("%b-%y"),
                    mom_delta=_amount_str(mom) if mom is not None else None,
                    yoy_delta=_amount_str(yoy) if yoy is not None else None,
                    currency_code=ccy,
                )
            )

    items.sort(key=lambda x: (x.revenue_month, x.customer_legal), reverse=True)
    return items
