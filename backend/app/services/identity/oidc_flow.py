"""OIDC discovery, authorization URL, code exchange, id_token validation."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


async def _get_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    r = await client.get(url, timeout=30.0)
    r.raise_for_status()
    return r.json()


async def fetch_oidc_metadata(issuer: str) -> dict[str, Any]:
    base = issuer.rstrip("/")
    meta_url = f"{base}/.well-known/openid-configuration"
    async with httpx.AsyncClient(follow_redirects=True) as client:
        return await _get_json(client, meta_url)


def merge_oidc_endpoints(meta: dict[str, Any], row_endpoints: dict[str, str | None]) -> dict[str, Any]:
    """Prefer DB overrides when set; else discovery document."""
    out = dict(meta)
    if row_endpoints.get("authorization_endpoint"):
        out["authorization_endpoint"] = row_endpoints["authorization_endpoint"]
    if row_endpoints.get("token_endpoint"):
        out["token_endpoint"] = row_endpoints["token_endpoint"]
    if row_endpoints.get("jwks_uri"):
        out["jwks_uri"] = row_endpoints["jwks_uri"]
    return out


def build_oidc_authorization_url(
    *,
    metadata: dict[str, Any],
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: str = "openid email profile",
) -> str:
    auth_ep = metadata["authorization_endpoint"]
    q = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
        }
    )
    sep = "&" if "?" in auth_ep else "?"
    return f"{auth_ep}{sep}{q}"


async def exchange_oidc_code(
    *,
    token_endpoint: str,
    client_id: str,
    client_secret: str | None,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
    }
    if client_secret:
        data["client_secret"] = client_secret
    async with httpx.AsyncClient() as client:
        r = await client.post(
            token_endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        if r.status_code >= 400:
            logger.warning("OIDC token endpoint error: %s %s", r.status_code, r.text[:500])
            r.raise_for_status()
        return r.json()


def decode_oidc_id_token(
    *,
    id_token: str,
    jwks_uri: str,
    client_id: str,
    issuer: str,
) -> dict[str, Any]:
    jwk_client = PyJWKClient(jwks_uri)
    signing_key = jwk_client.get_signing_key_from_jwt(id_token)
    return jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256", "RS384", "RS512", "ES256"],
        audience=client_id,
        issuer=issuer,
    )


async def fetch_oidc_userinfo(userinfo_url: str, access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()


def extract_oidc_email_and_groups(claims: dict[str, Any]) -> tuple[str, list[str] | None]:
    email = claims.get("email") or claims.get("preferred_username")
    if email and "@" not in str(email):
        email = None
    groups: list[str] | None = None
    raw = claims.get("groups")
    if raw is None:
        raw = claims.get("roles")
    if isinstance(raw, list):
        groups = [str(x) for x in raw]
    elif isinstance(raw, str) and raw:
        groups = [raw]
    if not email:
        raise ValueError("OIDC token missing email claim")
    return str(email).strip().lower(), groups
