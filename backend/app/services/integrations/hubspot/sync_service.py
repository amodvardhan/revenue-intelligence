"""Incremental HubSpot deal sync into fact_revenue and mapping exceptions."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimCustomer, DimOrganization
from app.models.facts import FactRevenue, IngestionBatch
from app.models.hubspot_integration import HubspotConnection, HubspotIdMapping, HubspotSyncCursor, IntegrationSyncRun
from app.services.integrations.hubspot.api_client import HubspotApiClient
from app.services.integrations.hubspot.connection_tokens import ensure_fresh_access_token
from app.services.integrations.hubspot.reconciliation import detect_revenue_conflicts

logger = logging.getLogger(__name__)

OBJECT_DEALS = "deals"


def _parse_hs_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        if value.isdigit():
            ms = int(value)
            return datetime.fromtimestamp(ms / 1000.0, tz=UTC).date()
        return date.fromisoformat(value[:10])
    except (ValueError, OSError):
        return None


def _deal_amount(props: dict[str, str | None]) -> Decimal:
    raw = props.get("amount")
    if raw in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return Decimal("0")


async def _default_org_id(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID | None:
    res = await session.execute(
        select(DimOrganization.org_id)
        .where(DimOrganization.tenant_id == tenant_id)
        .order_by(DimOrganization.created_at)
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _ensure_company_mapping_row(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_hs_id: str,
) -> HubspotIdMapping:
    res = await session.execute(
        select(HubspotIdMapping).where(
            HubspotIdMapping.tenant_id == tenant_id,
            HubspotIdMapping.hubspot_object_type == "company",
            HubspotIdMapping.hubspot_object_id == company_hs_id,
        )
    )
    row = res.scalar_one_or_none()
    if row:
        return row
    row = HubspotIdMapping(
        tenant_id=tenant_id,
        hubspot_object_type="company",
        hubspot_object_id=company_hs_id,
        status="pending",
    )
    session.add(row)
    await session.flush()
    return row


async def _ensure_deal_mapping_pending(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    deal_id: str,
) -> None:
    res = await session.execute(
        select(HubspotIdMapping).where(
            HubspotIdMapping.tenant_id == tenant_id,
            HubspotIdMapping.hubspot_object_type == "deal",
            HubspotIdMapping.hubspot_object_id == deal_id,
        )
    )
    if res.scalar_one_or_none():
        return
    session.add(
        HubspotIdMapping(
            tenant_id=tenant_id,
            hubspot_object_type="deal",
            hubspot_object_id=deal_id,
            status="pending",
        )
    )
    await session.flush()


async def _resolve_customer_for_company(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    company_hs_id: str,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    res = await session.execute(
        select(HubspotIdMapping).where(
            HubspotIdMapping.tenant_id == tenant_id,
            HubspotIdMapping.hubspot_object_type == "company",
            HubspotIdMapping.hubspot_object_id == company_hs_id,
            HubspotIdMapping.status == "mapped",
        )
    )
    m = res.scalar_one_or_none()
    if not m or not m.customer_id:
        return None, None
    res2 = await session.execute(select(DimCustomer).where(DimCustomer.customer_id == m.customer_id))
    cust = res2.scalar_one_or_none()
    if not cust:
        return None, None
    return cust.customer_id, cust.org_id


async def _upsert_deal_fact(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    deal_id: str,
    props: dict[str, str | None],
    org_id: uuid.UUID,
    customer_id: uuid.UUID | None,
) -> None:
    rev_date = _parse_hs_date(props.get("closedate")) or date.today()
    amount = _deal_amount(props)
    meta: dict[str, Any] = {
        "pipeline": props.get("pipeline"),
        "dealstage": props.get("dealstage"),
        "dealname": props.get("dealname"),
    }
    ins = insert(FactRevenue).values(
        tenant_id=tenant_id,
        amount=amount,
        currency_code="USD",
        revenue_date=rev_date,
        org_id=org_id,
        business_unit_id=None,
        division_id=None,
        customer_id=customer_id,
        revenue_type_id=None,
        source_system="hubspot",
        external_id=deal_id,
        source_metadata=meta,
        batch_id=batch_id,
        is_deleted=False,
        updated_at=func.now(),
    )
    ins = ins.on_conflict_do_update(
        constraint="uq_fact_revenue_source_external",
        set_={
            "amount": ins.excluded.amount,
            "revenue_date": ins.excluded.revenue_date,
            "org_id": ins.excluded.org_id,
            "customer_id": ins.excluded.customer_id,
            "source_metadata": ins.excluded.source_metadata,
            "batch_id": ins.excluded.batch_id,
            "is_deleted": ins.excluded.is_deleted,
            "updated_at": func.now(),
        },
    )
    await session.execute(ins)


async def _process_deal(
    session: AsyncSession,
    client: HubspotApiClient,
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    deal_id: str,
    str_props: dict[str, str | None],
    company_ids_from_assoc: list[str] | None,
) -> bool:
    """Return True if loaded, False if skipped."""
    company_ids = list(company_ids_from_assoc or [])
    if not company_ids:
        company_ids = await client.get_deal_company_ids(deal_id)
    if not company_ids:
        await _ensure_deal_mapping_pending(session, tenant_id=tenant_id, deal_id=deal_id)
        return False
    company_hs_id = company_ids[0]
    await _ensure_company_mapping_row(session, tenant_id=tenant_id, company_hs_id=company_hs_id)
    customer_id, org_from_customer = await _resolve_customer_for_company(session, tenant_id, company_hs_id)
    if customer_id is None:
        return False
    org_fallback = await _default_org_id(session, tenant_id)
    org_id = org_from_customer or org_fallback
    if org_id is None:
        return False
    await _upsert_deal_fact(
        session,
        tenant_id=tenant_id,
        batch_id=batch_id,
        deal_id=deal_id,
        props=str_props,
        org_id=org_id,
        customer_id=customer_id,
    )
    return True


async def run_hubspot_sync(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    sync_run_id: uuid.UUID,
    mode: str = "incremental",
) -> None:
    res = await session.execute(select(HubspotConnection).where(HubspotConnection.tenant_id == tenant_id))
    conn = res.scalar_one_or_none()
    if not conn:
        raise ValueError("HubSpot is not connected")

    run = await session.get(IntegrationSyncRun, sync_run_id)
    if not run or run.tenant_id != tenant_id:
        raise ValueError("Invalid sync run")

    try:
        access = await ensure_fresh_access_token(session, conn)
    except Exception as e:
        logger.exception("HubSpot token preparation failed")
        run.status = "failed"
        run.completed_at = datetime.now(tz=UTC)
        run.error_summary = str(e)[:2000]
        await session.flush()
        return

    if conn.status == "token_refresh_failed":
        run.status = "failed"
        run.completed_at = datetime.now(tz=UTC)
        run.error_summary = "Token refresh failed — reconnect HubSpot."
        await session.flush()
        return

    client = HubspotApiClient(access)

    res = await session.execute(
        select(HubspotSyncCursor).where(
            HubspotSyncCursor.tenant_id == tenant_id,
            HubspotSyncCursor.object_type == OBJECT_DEALS,
        )
    )
    cursor_row = res.scalar_one_or_none()
    payload = dict(cursor_row.cursor_payload) if cursor_row else {}
    last_ms = int(payload.get("last_modified_ms", 0))
    use_search = mode != "repair" and last_ms > 0

    batch = IngestionBatch(
        tenant_id=tenant_id,
        source_system="hubspot",
        filename=f"sync-{sync_run_id}.json",
        status="loading",
        initiated_by=run.initiated_by_user_id,
    )
    session.add(batch)
    await session.flush()

    fetched = loaded = failed = 0
    max_seen_ms = last_ms

    try:
        if use_search:
            after_cursor: str | None = None
            while True:
                page = await client.search_deals_modified_after(
                    after_ms=last_ms, limit=100, after_cursor=after_cursor
                )
                deals = page.get("results") or []
                for d in deals:
                    fetched += 1
                    deal_id = str(d.get("id", ""))
                    props = d.get("properties") or {}
                    str_props = {k: (str(v) if v is not None else None) for k, v in props.items()}
                    lmd = str_props.get("hs_lastmodifieddate")
                    if lmd and lmd.isdigit():
                        max_seen_ms = max(max_seen_ms, int(lmd))
                    try:
                        ok = await _process_deal(
                            session,
                            client,
                            tenant_id=tenant_id,
                            batch_id=batch.batch_id,
                            deal_id=deal_id,
                            str_props=str_props,
                            company_ids_from_assoc=None,
                        )
                        if ok:
                            loaded += 1
                        else:
                            failed += 1
                    except Exception:
                        logger.exception("deal sync failed id=%s", deal_id)
                        failed += 1

                paging = page.get("paging") or {}
                next_after = (paging.get("next") or {}).get("after")
                if not next_after:
                    break
                after_cursor = next_after
        else:
            after: str | None = None
            while True:
                page = await client.list_deals_page(limit=100, after=after)
                deals = page.get("results") or []
                for d in deals:
                    fetched += 1
                    deal_id = str(d.get("id", ""))
                    props = d.get("properties") or {}
                    str_props = {k: (str(v) if v is not None else None) for k, v in props.items()}
                    lmd = str_props.get("hs_lastmodifieddate")
                    if lmd and lmd.isdigit():
                        max_seen_ms = max(max_seen_ms, int(lmd))
                    try:
                        assoc = d.get("associations") or {}
                        company_results = ((assoc.get("companies") or {}).get("results")) or []
                        company_ids = [str(x.get("id")) for x in company_results if x.get("id")]
                        ok = await _process_deal(
                            session,
                            client,
                            tenant_id=tenant_id,
                            batch_id=batch.batch_id,
                            deal_id=deal_id,
                            str_props=str_props,
                            company_ids_from_assoc=company_ids,
                        )
                        if ok:
                            loaded += 1
                        else:
                            failed += 1
                    except Exception:
                        logger.exception("deal sync failed id=%s", deal_id)
                        failed += 1

                paging = page.get("paging") or {}
                next_link = (paging.get("next") or {}).get("after")
                if not next_link:
                    break
                after = next_link

        batch.status = "completed"
        batch.completed_at = datetime.now(tz=UTC)
        batch.loaded_rows = loaded
        batch.error_rows = failed
        run.rows_fetched = fetched
        run.rows_loaded = loaded
        run.rows_failed = failed
        if failed and loaded:
            run.status = "completed_with_errors"
        elif failed and not loaded:
            run.status = "failed"
        else:
            run.status = "completed"
        run.completed_at = datetime.now(tz=UTC)
        if failed and loaded:
            run.error_summary = f"{failed} deal(s) skipped (unmapped company or missing org)."
        elif failed:
            run.error_summary = "All deals failed validation or mapping."
        else:
            run.error_summary = None

        if cursor_row is None:
            cursor_row = HubspotSyncCursor(
                tenant_id=tenant_id,
                object_type=OBJECT_DEALS,
                cursor_payload={"last_modified_ms": max_seen_ms},
            )
            session.add(cursor_row)
        else:
            cursor_row.cursor_payload = {"last_modified_ms": max(max_seen_ms, last_ms)}
            cursor_row.updated_at = datetime.now(tz=UTC)

        await detect_revenue_conflicts(session, tenant_id=tenant_id)
        await session.flush()
    except Exception as e:
        logger.exception("HubSpot sync run failed")
        batch.status = "failed"
        batch.completed_at = datetime.now(tz=UTC)
        run.status = "failed"
        run.completed_at = datetime.now(tz=UTC)
        run.error_summary = str(e)[:2000]
        await session.flush()
