"""Encrypt HubSpot token bundles at rest (Fernet with key derived from SECRET_KEY)."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_token_bundle(data: dict[str, Any]) -> str:
    """Serialize and encrypt OAuth tokens + metadata."""
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(raw).decode("ascii")


def decrypt_token_bundle(ciphertext: str) -> dict[str, Any]:
    raw = _fernet().decrypt(ciphertext.encode("ascii"))
    return json.loads(raw.decode("utf-8"))
