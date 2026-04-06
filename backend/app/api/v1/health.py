"""Health check (no auth)."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Service health",
    description="Liveness probe; no authentication required.",
)
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
