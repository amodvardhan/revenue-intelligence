"""Signed OAuth state (CSRF) for HubSpot connect flow."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings


def create_oauth_state(*, tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "typ": "hubspot_oauth",
        "tid": str(tenant_id),
        "uid": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def parse_oauth_state(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    settings = get_settings()
    data = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    if data.get("typ") != "hubspot_oauth":
        raise ValueError("invalid state type")
    return uuid.UUID(data["tid"]), uuid.UUID(data["uid"])
