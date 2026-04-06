"""Manual FX table: lookup by pair and effective date — no silent fallback."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase5 import FxRate


def _quantize_money(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.0001"))


async def get_rate_for_pair(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    base_currency_code: str,
    quote_currency_code: str,
    as_of_date: date,
) -> FxRate | None:
    """Return latest rate row with effective_date <= as_of for the pair (base → quote)."""
    base_currency_code = base_currency_code.upper().strip()
    quote_currency_code = quote_currency_code.upper().strip()
    if base_currency_code == quote_currency_code:
        return None

    stmt = (
        select(FxRate)
        .where(
            and_(
                FxRate.tenant_id == tenant_id,
                FxRate.base_currency_code == base_currency_code,
                FxRate.quote_currency_code == quote_currency_code,
                FxRate.effective_date <= as_of_date,
            )
        )
        .order_by(desc(FxRate.effective_date))
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_inverse_rate_for_pair(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    base_currency_code: str,
    quote_currency_code: str,
    as_of_date: date,
) -> FxRate | None:
    """If direct pair missing, try inverse (quote → base) and invert the numeric rate."""
    inv = await get_rate_for_pair(
        session,
        tenant_id=tenant_id,
        base_currency_code=quote_currency_code,
        quote_currency_code=base_currency_code,
        as_of_date=as_of_date,
    )
    return inv


async def convert_to_reporting_currency(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    amount: Decimal,
    native_currency_code: str,
    reporting_currency_code: str,
    as_of_date: date,
) -> tuple[Decimal, FxRate | None, str]:
    """
    Convert amount from native to reporting using stored rates.
    Rate convention: 1 unit base = `rate` units quote (quote is reporting when pair is native→reporting).

    Returns (converted_amount, fx_rate_row_or_none_if_identity, conversion_note).
    """
    native_currency_code = native_currency_code.upper().strip()
    reporting_currency_code = reporting_currency_code.upper().strip()
    if native_currency_code == reporting_currency_code:
        return _quantize_money(amount), None, "native_equals_reporting"

    direct = await get_rate_for_pair(
        session,
        tenant_id=tenant_id,
        base_currency_code=native_currency_code,
        quote_currency_code=reporting_currency_code,
        as_of_date=as_of_date,
    )
    if direct is not None:
        return _quantize_money(amount * direct.rate), direct, "direct_pair"

    inv = await get_inverse_rate_for_pair(
        session,
        tenant_id=tenant_id,
        base_currency_code=native_currency_code,
        quote_currency_code=reporting_currency_code,
        as_of_date=as_of_date,
    )
    if inv is not None:
        # inv: base=reporting, quote=native — 1 reporting = inv.rate native → amount_native / inv.rate
        if inv.rate == 0:
            raise ValueError("FX_RATE_INVALID")
        return _quantize_money(amount / inv.rate), inv, "inverted_pair"

    raise LookupError("FX_RATE_MISSING")
