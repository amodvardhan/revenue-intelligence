"""HubSpot integration — OAuth, sync, mapping, conflicts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import (
    require_conflict_patch_role,
    require_hubspot_connect_role,
    require_hubspot_enabled,
    require_hubspot_read_role,
    require_hubspot_sync_role,
    require_mapping_patch_role,
)
from app.models.hubspot_integration import (
    HubspotConnection,
    HubspotIdMapping,
    IntegrationSyncRun,
    RevenueSourceConflict,
)
from app.models.tenant import User
from app.services.integrations.hubspot.crypto_bundle import encrypt_token_bundle
from app.services.integrations.hubspot.oauth_authorize import build_authorization_url
from app.services.integrations.hubspot.oauth_state import create_oauth_state, parse_oauth_state
from app.services.integrations.hubspot.oauth_tokens import exchange_authorization_code
from app.services.integrations.hubspot.portal import fetch_portal_id
router = APIRouter(prefix="/integrations/hubspot", tags=["hubspot"])


class SyncRequest(BaseModel):
    mode: str = Field(default="incremental", description="incremental | repair")
    correlation_id: uuid.UUID | None = None


class DisconnectResponse(BaseModel):
    status: str


class MappingPatch(BaseModel):
    customer_id: uuid.UUID | None = None
    org_id: uuid.UUID | None = None
    status: str | None = None
    notes: str | None = None


class ConflictPatch(BaseModel):
    status: str
    resolution_notes: str | None = None


@router.get(
    "/oauth/authorize-url",
    summary="HubSpot OAuth — start URL + CSRF state",
    dependencies=[Depends(require_hubspot_enabled)],
)
async def get_authorize_url(
    user: User = Depends(require_hubspot_connect_role),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    res = await session.execute(select(HubspotConnection).where(HubspotConnection.tenant_id == user.tenant_id))
    conn = res.scalar_one_or_none()
    if conn and conn.status == "connected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "IMPORT_OVERLAP", "message": "HubSpot already connected", "details": None}},
        )
    state = create_oauth_state(tenant_id=user.tenant_id, user_id=user.user_id)
    url = build_authorization_url(state=state)
    return {"authorization_url": url, "state": state}


@router.get("/oauth/callback", summary="HubSpot OAuth redirect target")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    if not settings.ENABLE_HUBSPOT:
        base = settings.HUBSPOT_FRONTEND_REDIRECT_BASE
        return RedirectResponse(url=f"{base}?hubspot=error&reason=disabled", status_code=302)
    try:
        tenant_id, user_id = parse_oauth_state(state)
    except Exception:
        base = settings.HUBSPOT_FRONTEND_REDIRECT_BASE
        return RedirectResponse(url=f"{base}?hubspot=error&reason=state", status_code=302)

    from sqlalchemy import text

    await session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
    await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)})

    try:
        tokens = await exchange_authorization_code(code)
    except Exception:
        base = settings.HUBSPOT_FRONTEND_REDIRECT_BASE
        return RedirectResponse(url=f"{base}?hubspot=error&reason=token", status_code=302)

    access = tokens["access_token"]
    refresh = tokens.get("refresh_token", "")
    expires_in = int(tokens.get("expires_in", 1800))
    bundle = {"access_token": access, "refresh_token": refresh}
    portal = await fetch_portal_id(access)
    now = datetime.now(tz=UTC)

    res = await session.execute(select(HubspotConnection).where(HubspotConnection.tenant_id == tenant_id))
    conn_row = res.scalar_one_or_none()
    if conn_row is None:
        conn_row = HubspotConnection(
            tenant_id=tenant_id,
            status="connected",
            hubspot_portal_id=portal,
            encrypted_token_bundle=encrypt_token_bundle(bundle),
            token_expires_at=now + timedelta(seconds=expires_in),
            scopes_granted=tokens.get("scope"),
            last_token_refresh_at=now,
            connected_by_user_id=user_id,
        )
        session.add(conn_row)
    else:
        conn_row.status = "connected"
        conn_row.hubspot_portal_id = portal or conn_row.hubspot_portal_id
        conn_row.encrypted_token_bundle = encrypt_token_bundle(bundle)
        conn_row.token_expires_at = now + timedelta(seconds=expires_in)
        conn_row.scopes_granted = tokens.get("scope") or conn_row.scopes_granted
        conn_row.last_token_refresh_at = now
        conn_row.last_error = None
        conn_row.connected_by_user_id = user_id
    await session.commit()

    base = settings.HUBSPOT_FRONTEND_REDIRECT_BASE
    return RedirectResponse(url=f"{base}?connected=1", status_code=302)


@router.get("/status", dependencies=[Depends(require_hubspot_enabled)])
async def hubspot_status(
    user: User = Depends(require_hubspot_read_role),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await session.execute(select(HubspotConnection).where(HubspotConnection.tenant_id == user.tenant_id))
    conn = res.scalar_one_or_none()
    if not conn:
        return {
            "status": "disconnected",
            "hubspot_portal_id": None,
            "token_expires_at": None,
            "last_token_refresh_at": None,
            "last_error": None,
            "scopes_granted": None,
        }
    return {
        "status": conn.status,
        "hubspot_portal_id": conn.hubspot_portal_id,
        "token_expires_at": conn.token_expires_at.isoformat().replace("+00:00", "Z")
        if conn.token_expires_at
        else None,
        "last_token_refresh_at": conn.last_token_refresh_at.isoformat().replace("+00:00", "Z")
        if conn.last_token_refresh_at
        else None,
        "last_error": conn.last_error,
        "scopes_granted": conn.scopes_granted,
    }


@router.post("/disconnect", dependencies=[Depends(require_hubspot_enabled)])
async def hubspot_disconnect(
    user: User = Depends(require_hubspot_connect_role),
    session: AsyncSession = Depends(get_db),
) -> DisconnectResponse:
    res = await session.execute(select(HubspotConnection).where(HubspotConnection.tenant_id == user.tenant_id))
    conn = res.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "No HubSpot connection", "details": None}},
        )
    conn.status = "disconnected"
    conn.encrypted_token_bundle = None
    conn.token_expires_at = None
    conn.last_error = None
    await session.commit()
    return DisconnectResponse(status="disconnected")


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_hubspot_enabled)])
async def trigger_sync(
    body: SyncRequest,
    user: User = Depends(require_hubspot_sync_role),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await session.execute(
        select(IntegrationSyncRun).where(
            IntegrationSyncRun.tenant_id == user.tenant_id,
            IntegrationSyncRun.status == "running",
        )
    )
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "IMPORT_OVERLAP", "message": "Sync already running", "details": None}},
        )
    cid = body.correlation_id or uuid.uuid4()
    run = IntegrationSyncRun(
        tenant_id=user.tenant_id,
        integration_code="hubspot",
        trigger="manual",
        initiated_by_user_id=user.user_id,
        status="running",
        correlation_id=cid,
    )
    session.add(run)
    await session.flush()
    mode = body.mode if body.mode in ("incremental", "repair") else "incremental"
    from app.tasks.sync_tasks import run_hubspot_sync_task

    run_hubspot_sync_task.delay(str(run.sync_run_id), str(user.tenant_id), mode)
    await session.commit()
    return {
        "sync_run_id": str(run.sync_run_id),
        "status": "running",
        "message": "Sync accepted",
    }


@router.get("/sync-runs", dependencies=[Depends(require_hubspot_enabled)])
async def list_sync_runs(
    user: User = Depends(require_hubspot_read_role),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    res = await session.execute(
        select(IntegrationSyncRun)
        .where(
            IntegrationSyncRun.tenant_id == user.tenant_id,
            IntegrationSyncRun.integration_code == "hubspot",
        )
        .order_by(IntegrationSyncRun.started_at.desc())
        .limit(limit)
    )
    rows = res.scalars().all()
    items = []
    for r in rows:
        items.append(
            {
                "sync_run_id": str(r.sync_run_id),
                "trigger": r.trigger,
                "status": r.status,
                "started_at": r.started_at.isoformat().replace("+00:00", "Z"),
                "completed_at": r.completed_at.isoformat().replace("+00:00", "Z") if r.completed_at else None,
                "rows_fetched": r.rows_fetched,
                "rows_loaded": r.rows_loaded,
                "rows_failed": r.rows_failed,
                "error_summary": r.error_summary,
                "correlation_id": str(r.correlation_id) if r.correlation_id else None,
            }
        )
    return {"items": items, "next_cursor": None}


@router.get("/sync-runs/{sync_run_id}", dependencies=[Depends(require_hubspot_enabled)])
async def get_sync_run(
    sync_run_id: uuid.UUID,
    user: User = Depends(require_hubspot_read_role),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    r = await session.get(IntegrationSyncRun, sync_run_id)
    if not r or r.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Sync run not found", "details": None}},
        )
    return {
        "sync_run_id": str(r.sync_run_id),
        "trigger": r.trigger,
        "status": r.status,
        "stats": r.stats,
        "started_at": r.started_at.isoformat().replace("+00:00", "Z"),
        "completed_at": r.completed_at.isoformat().replace("+00:00", "Z") if r.completed_at else None,
        "rows_fetched": r.rows_fetched,
        "rows_loaded": r.rows_loaded,
        "rows_failed": r.rows_failed,
        "error_summary": r.error_summary,
        "correlation_id": str(r.correlation_id) if r.correlation_id else None,
    }


@router.get("/mapping-exceptions", dependencies=[Depends(require_hubspot_enabled)])
async def mapping_exceptions(
    user: User = Depends(require_hubspot_read_role),
    session: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    q = select(HubspotIdMapping).where(HubspotIdMapping.tenant_id == user.tenant_id)
    if status_filter:
        q = q.where(HubspotIdMapping.status == status_filter)
    else:
        q = q.where(HubspotIdMapping.status.in_(("pending", "ambiguous")))
    q = q.order_by(HubspotIdMapping.updated_at.desc()).limit(limit)
    res = await session.execute(q)
    rows = res.scalars().all()
    items = []
    for m in rows:
        items.append(
            {
                "mapping_id": str(m.mapping_id),
                "hubspot_object_type": m.hubspot_object_type,
                "hubspot_object_id": m.hubspot_object_id,
                "status": m.status,
                "customer_id": str(m.customer_id) if m.customer_id else None,
                "notes": m.notes,
            }
        )
    return {"items": items, "next_cursor": None}


@router.patch("/mapping-exceptions/{mapping_id}", dependencies=[Depends(require_hubspot_enabled)])
async def patch_mapping(
    mapping_id: uuid.UUID,
    body: MappingPatch,
    user: User = Depends(require_mapping_patch_role),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    m = await session.get(HubspotIdMapping, mapping_id)
    if not m or m.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Mapping not found", "details": None}},
        )
    if body.customer_id is not None:
        m.customer_id = body.customer_id
    if body.org_id is not None:
        m.org_id = body.org_id
    if body.status is not None:
        m.status = body.status
    if body.notes is not None:
        m.notes = body.notes
    m.updated_at = datetime.now(tz=UTC)
    await session.commit()
    return {
        "mapping_id": str(m.mapping_id),
        "hubspot_object_type": m.hubspot_object_type,
        "hubspot_object_id": m.hubspot_object_id,
        "status": m.status,
        "customer_id": str(m.customer_id) if m.customer_id else None,
        "org_id": str(m.org_id) if m.org_id else None,
        "notes": m.notes,
    }


@router.get("/revenue-conflicts", dependencies=[Depends(require_hubspot_enabled)])
async def list_conflicts(
    user: User = Depends(require_hubspot_read_role),
    session: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    q = select(RevenueSourceConflict).where(RevenueSourceConflict.tenant_id == user.tenant_id)
    if status_filter:
        q = q.where(RevenueSourceConflict.status == status_filter)
    q = q.order_by(RevenueSourceConflict.detected_at.desc()).limit(limit)
    res = await session.execute(q)
    rows = res.scalars().all()
    items = []
    for c in rows:
        items.append(
            {
                "conflict_id": str(c.conflict_id),
                "reconciliation_key": c.reconciliation_key,
                "excel_amount": format(c.excel_amount, "f") if c.excel_amount is not None else None,
                "hubspot_amount": format(c.hubspot_amount, "f") if c.hubspot_amount is not None else None,
                "status": c.status,
                "detected_at": c.detected_at.isoformat().replace("+00:00", "Z"),
            }
        )
    return {"items": items, "next_cursor": None}


@router.patch("/revenue-conflicts/{conflict_id}", dependencies=[Depends(require_hubspot_enabled)])
async def patch_conflict(
    conflict_id: uuid.UUID,
    body: ConflictPatch,
    user: User = Depends(require_conflict_patch_role),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    c = await session.get(RevenueSourceConflict, conflict_id)
    if not c or c.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Conflict not found", "details": None}},
        )
    c.status = body.status
    if body.resolution_notes is not None:
        c.resolution_notes = body.resolution_notes
    c.updated_at = datetime.now(tz=UTC)
    await session.commit()
    return {
        "conflict_id": str(c.conflict_id),
        "status": c.status,
        "resolution_notes": c.resolution_notes,
    }
