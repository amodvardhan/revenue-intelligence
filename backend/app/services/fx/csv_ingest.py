"""Load fx_rate rows from CSV."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase5 import FxRate


async def load_fx_csv(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    file_bytes: bytes,
    batch_id: uuid.UUID | None,
    rate_source: str = "manual_upload",
) -> int:
    """CSV: base_currency_code, quote_currency_code, effective_date, rate[,notes]."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Empty CSV")
    fields = {h.strip().lower() for h in reader.fieldnames if h}
    req = {"base_currency_code", "quote_currency_code", "effective_date", "rate"}
    if not req.issubset(fields):
        raise ValueError("CSV must have base_currency_code, quote_currency_code, effective_date, rate")

    n = 0
    for row in reader:
        r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        base = r["base_currency_code"].upper()[:3]
        quote = r["quote_currency_code"].upper()[:3]
        ed = date.fromisoformat(r["effective_date"])
        rate = Decimal(r["rate"])
        notes = r.get("notes") or None
        fx = FxRate(
            tenant_id=tenant_id,
            base_currency_code=base,
            quote_currency_code=quote,
            effective_date=ed,
            rate=rate,
            rate_source=rate_source,
            notes=notes,
            ingestion_batch_id=batch_id,
        )
        session.add(fx)
        n += 1
    await session.flush()
    return n
