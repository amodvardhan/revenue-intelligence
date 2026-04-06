"""Phase 6 — tenant security visibility, audit export, admin operations summary."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_audit_export_permission, require_tenant_sso_admin
from app.models.audit import AuditEvent
from app.models.phase6_governance import SsoProviderConfig
from app.models.tenant import Tenant, User
from app.services.admin_operations_service import build_operations_summary
from app.services.audit_export_service import collect_audit_export_rows, rows_to_csv_bytes, rows_to_jsonl_bytes
from app.services.identity.federation import get_security_settings

router = APIRouter(tags=["phase6-governance"])


class TenantSecurityOut(BaseModel):
    tenant_id: uuid.UUID
    reporting_currency_code: str
    invite_only: bool
    require_sso_for_standard_users: bool
    sso_oidc_enabled: bool
    sso_saml_enabled: bool
    retention_notice_label: str | None
    idle_timeout_minutes: int | None
    absolute_timeout_minutes: int | None


class TenantSecurityPatch(BaseModel):
    invite_only: bool | None = None
    require_sso_for_standard_users: bool | None = None
    retention_notice_label: str | None = None
    idle_timeout_minutes: int | None = None
    absolute_timeout_minutes: int | None = None


async def _tenant_security_response(session: AsyncSession, user: User) -> TenantSecurityOut:
    tres = await session.execute(select(Tenant).where(Tenant.tenant_id == user.tenant_id))
    tenant = tres.scalar_one()
    sec = await get_security_settings(session, user.tenant_id)
    oidc = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == user.tenant_id,
            SsoProviderConfig.protocol == "oidc",
        )
    )
    oidc_row = oidc.scalar_one_or_none()
    saml = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == user.tenant_id,
            SsoProviderConfig.protocol == "saml",
        )
    )
    saml_row = saml.scalar_one_or_none()
    return TenantSecurityOut(
        tenant_id=user.tenant_id,
        reporting_currency_code=tenant.default_currency_code,
        invite_only=sec.invite_only,
        require_sso_for_standard_users=sec.require_sso_for_standard_users,
        sso_oidc_enabled=bool(oidc_row and oidc_row.is_enabled),
        sso_saml_enabled=bool(saml_row and saml_row.is_enabled),
        retention_notice_label=sec.retention_notice_label
        or "Operational audit retention: 365 days (default)",
        idle_timeout_minutes=sec.idle_timeout_minutes,
        absolute_timeout_minutes=sec.absolute_timeout_minutes,
    )


@router.get("/tenant/security", response_model=TenantSecurityOut)
async def get_tenant_security(
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> TenantSecurityOut:
    return await _tenant_security_response(session, user)


@router.patch("/tenant/security", response_model=TenantSecurityOut)
async def patch_tenant_security(
    body: TenantSecurityPatch,
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> TenantSecurityOut:
    sec = await get_security_settings(session, user.tenant_id)
    if body.invite_only is not None:
        sec.invite_only = body.invite_only
    if body.require_sso_for_standard_users is not None:
        sec.require_sso_for_standard_users = body.require_sso_for_standard_users
    if body.retention_notice_label is not None:
        sec.retention_notice_label = body.retention_notice_label
    if body.idle_timeout_minutes is not None:
        sec.idle_timeout_minutes = body.idle_timeout_minutes
    if body.absolute_timeout_minutes is not None:
        sec.absolute_timeout_minutes = body.absolute_timeout_minutes
    session.add(
        AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            action="tenant.security.patch",
            entity_type="tenant_security_settings",
            entity_id=user.tenant_id,
            payload=body.model_dump(exclude_none=True),
        )
    )
    await session.commit()
    return await _tenant_security_response(session, user)


class AuditExportRequest(BaseModel):
    event_families: list[str] = Field(min_length=1)
    created_from: datetime
    created_to: datetime
    format: str = Field(pattern="^(csv|jsonl)$")


@router.post("/audit/exports")
async def post_audit_export(
    body: AuditExportRequest,
    user: User = Depends(require_audit_export_permission),
    session: AsyncSession = Depends(get_db),
) -> Response:
    settings = get_settings()
    allowed = {"ingestion", "nl_query", "hubspot_sync", "sso_security"}
    families = [f for f in body.event_families if f in allowed]
    if not families:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "No valid event_families", "details": None}},
        )
    if body.created_to <= body.created_from:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "created_to must be after created_from", "details": None}},
        )
    if (body.created_to - body.created_from).days > 400:
        raise HTTPException(
            status_code=413,
            detail={
                "error": {
                    "code": "AUDIT_EXPORT_TOO_LARGE",
                    "message": "Date range exceeds 400 days — narrow the export window",
                    "details": None,
                }
            },
        )
    rows = await collect_audit_export_rows(
        session,
        tenant_id=user.tenant_id,
        event_families=families,
        created_from=body.created_from,
        created_to=body.created_to,
        max_rows=settings.AUDIT_EXPORT_MAX_ROWS,
    )
    row_count_estimate = len(rows)
    session.add(
        AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            action="audit_export.completed",
            entity_type="audit_export",
            entity_id=uuid.uuid4(),
            payload={
                "families": families,
                "created_from": body.created_from.isoformat(),
                "created_to": body.created_to.isoformat(),
                "format": body.format,
                "row_count": row_count_estimate,
            },
        )
    )
    await session.commit()
    if body.format == "csv":
        data = rows_to_csv_bytes(rows)
        return Response(
            content=data,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="audit-export.csv"'},
        )
    data = rows_to_jsonl_bytes(rows)
    return Response(
        content=data,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="audit-export.jsonl"'},
    )


@router.get("/admin/operations/summary")
async def get_operations_summary(
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await build_operations_summary(session, user.tenant_id)
