"""Governed semantic layer version read (Phase 3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_query_audit_role
from app.models.nl_semantic import SemanticLayerVersion
from app.models.tenant import User
from app.schemas.query import SemanticVersionResponse

router = APIRouter(prefix="/semantic-layer", tags=["semantic-layer"])


@router.get(
    "/version",
    summary="Active semantic layer version",
    description="Story 3.1 traceability — optional governance read.",
)
async def get_semantic_version(
    user: User = Depends(require_query_audit_role),
    session: AsyncSession = Depends(get_db),
) -> SemanticVersionResponse:
    res = await session.execute(
        select(SemanticLayerVersion).where(
            SemanticLayerVersion.tenant_id == user.tenant_id,
            SemanticLayerVersion.is_active.is_(True),
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "No active semantic layer version",
                    "details": None,
                }
            },
        )
    return SemanticVersionResponse(
        version_id=row.version_id,
        version_label=row.version_label,
        source_identifier=row.source_identifier,
        content_sha256=row.content_sha256,
        effective_from=row.effective_from.isoformat().replace("+00:00", "Z"),
        is_active=row.is_active,
    )
