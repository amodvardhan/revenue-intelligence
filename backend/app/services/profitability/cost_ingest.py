"""Load fact_cost from CSV."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase5 import FactCost


async def load_cost_csv(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_id: uuid.UUID,
    default_category: str,
    file_bytes: bytes,
    batch_id: uuid.UUID,
    source_system: str = "cost_excel",
) -> int:
    """CSV: cost_date, amount, currency_code[,business_unit_id,customer_id,cost_category,external_id]."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Empty CSV")
    fields = {h.strip().lower() for h in reader.fieldnames if h}
    if not {"cost_date", "amount", "currency_code"}.issubset(fields):
        raise ValueError("CSV must have cost_date, amount, currency_code")

    loaded = 0
    for i, row in enumerate(reader):
        r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        cd = date.fromisoformat(r["cost_date"])
        amt = Decimal(r["amount"])
        ccy = r["currency_code"].upper()[:3]
        cat = (r.get("cost_category") or default_category)[:100]
        bu = uuid.UUID(r["business_unit_id"]) if r.get("business_unit_id") else None
        cust = uuid.UUID(r["customer_id"]) if r.get("customer_id") else None
        ext = (r.get("external_id") or f"cost-{i}")[:255]
        fc = FactCost(
            tenant_id=tenant_id,
            amount=amt,
            currency_code=ccy,
            cost_date=cd,
            cost_category=cat,
            org_id=org_id,
            business_unit_id=bu,
            division_id=None,
            customer_id=cust,
            source_system=source_system,
            external_id=ext,
            batch_id=batch_id,
        )
        session.add(fc)
        loaded += 1
    await session.flush()
    return loaded
