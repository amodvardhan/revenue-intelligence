"""Tenant reporting currency (Phase 5)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_user,
    require_phase5_enabled,
    require_tenant_settings_write_role,
)
from app.models.tenant import Tenant, User

router = APIRouter(prefix="/tenant", tags=["tenant"])

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


@router.get(
    "/settings",
    summary="Get tenant settings",
    description="Reporting currency alias (tenants.default_currency_code). Phase 5.",
    dependencies=[Depends(require_phase5_enabled)],
)
async def get_tenant_settings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    t = await session.get(Tenant, user.tenant_id)
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Tenant not found", "details": None}},
        )
    return {
        "tenant_id": str(t.tenant_id),
        "reporting_currency_code": t.default_currency_code.upper(),
        "notes": "Alias of default_currency_code per database-schema.md",
    }


@router.patch(
    "/settings",
    summary="Update tenant settings",
    description="Update reporting currency (ISO 4217).",
)
async def patch_tenant_settings(
    body: dict,
    user: User = Depends(require_tenant_settings_write_role),
    session: AsyncSession = Depends(get_db),
) -> dict:
    code = body.get("reporting_currency_code")
    if not code or not _CURRENCY_RE.match(str(code).upper()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid ISO currency code",
                    "details": None,
                }
            },
        )
    t = await session.get(Tenant, user.tenant_id)
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Tenant not found", "details": None}},
        )
    t.default_currency_code = str(code).upper()[:3]
    await session.flush()
    await session.commit()
    return {
        "tenant_id": str(t.tenant_id),
        "reporting_currency_code": t.default_currency_code,
        "notes": "Alias of default_currency_code per database-schema.md",
    }
