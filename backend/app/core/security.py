"""Password hashing and JWT helpers."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

# bcrypt rejects inputs > 72 bytes; SHA-256 pre-hash keeps long passphrases usable.
_BCRYPT_MAX_PASSWORD_BYTES = 72


def _password_digest(plain: str) -> bytes:
    raw = plain.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_PASSWORD_BYTES:
        return hashlib.sha256(raw).digest()
    return raw


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt (compatible with standard $2b$ hashes)."""
    return bcrypt.hashpw(_password_digest(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash string."""
    try:
        return bcrypt.checkpw(_password_digest(plain), hashed.encode("ascii"))
    except ValueError:
        return False


def create_access_token(*, subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=3600)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise ValueError("Invalid or expired token") from e


def create_sso_state_token(*, tenant_id: str, protocol: str) -> str:
    """Short-lived signed state for OIDC/SAML CSRF protection (query param round-trip)."""
    import secrets

    settings = get_settings()
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": "sso-state",
        "purpose": "sso_callback",
        "tenant_id": tenant_id,
        "protocol": protocol,
        "nonce": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_sso_state_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise ValueError("Invalid SSO state") from e
    if payload.get("sub") != "sso-state" or payload.get("purpose") != "sso_callback":
        raise ValueError("Invalid SSO state")
    return payload
