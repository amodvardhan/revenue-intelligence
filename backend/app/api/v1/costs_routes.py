"""Cost facts and allocation rules (Phase 5)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_user,
    require_cost_allocation_role,
    require_phase5_enabled,
)
from app.models.phase5 import CostAllocationRule, FactCost
from app.models.tenant import User
from app.services.access_scope import accessible_org_ids

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get(
    "/facts",
    summary="List cost facts",
    dependencies=[Depends(require_phase5_enabled)],
)
async def list_cost_facts(
    cost_date_from: date | None = None,
    cost_date_to: date | None = None,
    org_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    customer_id: UUID | None = None,
    cost_category: str | None = None,
    source_system: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    limit = min(max(limit, 1), 200)
    acc = await accessible_org_ids(session, user.user_id)
    f = [FactCost.tenant_id == user.tenant_id, FactCost.org_id.in_(acc)]
    if org_id:
        if org_id not in acc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Org not accessible", "details": None}},
            )
        f.append(FactCost.org_id == org_id)
    if cost_date_from:
        f.append(FactCost.cost_date >= cost_date_from)
    if cost_date_to:
        f.append(FactCost.cost_date <= cost_date_to)
    if business_unit_id:
        f.append(FactCost.business_unit_id == business_unit_id)
    if customer_id:
        f.append(FactCost.customer_id == customer_id)
    if cost_category:
        f.append(FactCost.cost_category == cost_category)
    if source_system:
        f.append(FactCost.source_system == source_system)
    stmt = select(FactCost).where(and_(*f)).order_by(FactCost.cost_date.desc()).limit(limit)
    res = await session.execute(stmt)
    items = []
    for r in res.scalars().all():
        items.append(
            {
                "cost_fact_id": str(r.cost_fact_id),
                "amount": format(r.amount, "f"),
                "currency_code": r.currency_code,
                "cost_date": r.cost_date.isoformat(),
                "cost_category": r.cost_category,
                "org_id": str(r.org_id),
                "business_unit_id": str(r.business_unit_id) if r.business_unit_id else None,
                "customer_id": str(r.customer_id) if r.customer_id else None,
                "source_system": r.source_system,
            }
        )
    return {"items": items, "next_cursor": None}


@router.get(
    "/allocation-rules",
    summary="List cost allocation rules",
    dependencies=[Depends(require_phase5_enabled)],
)
async def list_allocation_rules(
    effective_on: date | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(CostAllocationRule).where(CostAllocationRule.tenant_id == user.tenant_id)
    if effective_on:
        stmt = stmt.where(
            and_(
                CostAllocationRule.effective_from <= effective_on,
                (CostAllocationRule.effective_to.is_(None))
                | (CostAllocationRule.effective_to >= effective_on),
            )
        )
    stmt = stmt.order_by(CostAllocationRule.effective_from.desc())
    res = await session.execute(stmt)
    items = []
    for r in res.scalars().all():
        items.append(
            {
                "rule_id": str(r.rule_id),
                "version_label": r.version_label,
                "effective_from": r.effective_from.isoformat(),
                "effective_to": r.effective_to.isoformat() if r.effective_to else None,
                "basis": r.basis,
                "rule_definition": r.rule_definition,
            }
        )
    return {"items": items}


@router.post(
    "/allocation-rules",
    summary="Create allocation rule",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_phase5_enabled)],
)
async def create_allocation_rule(
    body: dict,
    user: User = Depends(require_cost_allocation_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    rule = CostAllocationRule(
        tenant_id=user.tenant_id,
        version_label=str(body.get("version_label", "v1"))[:100],
        effective_from=date.fromisoformat(body["effective_from"]),
        effective_to=date.fromisoformat(body["effective_to"]) if body.get("effective_to") else None,
        basis=str(body.get("basis", "revenue_share"))[:50],
        rule_definition=body.get("rule_definition") or {},
        created_by_user_id=user.user_id,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return {"rule_id": str(rule.rule_id), "version_label": rule.version_label}
