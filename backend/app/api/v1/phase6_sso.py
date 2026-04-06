"""Phase 6 — public SSO routes (OIDC / SAML) and tenant SSO admin APIs."""

from __future__ import annotations

import logging
import uuid
from time import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_tenant_sso_admin
from app.core.security import create_access_token, create_sso_state_token, decode_sso_state_token
from app.models.phase6_governance import (
    IdpGroupRoleMapping,
    SsoProviderConfig,
    TenantEmailDomainAllowlist,
)
from app.models.tenant import User
from app.services.identity.federation import FederatedLoginError, provision_or_login_federated_user
from app.services.identity.oidc_flow import (
    build_oidc_authorization_url,
    decode_oidc_id_token,
    exchange_oidc_code,
    extract_oidc_email_and_groups,
    fetch_oidc_metadata,
    merge_oidc_endpoints,
)
from app.services.identity.saml_flow import (
    build_authn_request_redirect_url,
    build_sp_metadata_xml,
    decode_saml_post,
    fetch_saml_metadata_xml,
    parse_idp_sso_url_and_cert,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["phase6-sso"])

_sso_rate: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limit_sso(request: Request) -> None:
    settings = get_settings()
    ip = _client_ip(request)
    now = time()
    window = 60.0
    bucket = _sso_rate.setdefault(ip, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= settings.SSO_CALLBACK_RATE_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "RATE_LIMIT", "message": "Too many SSO requests", "details": None}},
        )
    bucket.append(now)


def _oidc_redirect_uri() -> str:
    s = get_settings()
    return f"{s.PUBLIC_API_BASE_URL.rstrip('/')}/api/v1/auth/sso/oidc/callback"


def _saml_acs_url() -> str:
    s = get_settings()
    return f"{s.PUBLIC_API_BASE_URL.rstrip('/')}/api/v1/auth/sso/saml/acs"


def _frontend_redirect_with_token(access_token: str) -> RedirectResponse:
    s = get_settings()
    base = s.FRONTEND_PUBLIC_BASE_URL.rstrip("/")
    url = f"{base}/login?sso=1&access_token={access_token}&token_type=bearer"
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/auth/sso/oidc/login")
async def oidc_login(
    request: Request,
    tenant_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    if not settings.ENABLE_SSO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "SSO_NOT_CONFIGURED", "message": "SSO disabled", "details": None}},
        )
    _rate_limit_sso(request)
    res = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == tenant_id,
            SsoProviderConfig.protocol == "oidc",
            SsoProviderConfig.is_enabled.is_(True),
        )
    )
    row = res.scalar_one_or_none()
    if row is None or not row.oidc_issuer or not row.oidc_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "SSO_NOT_CONFIGURED", "message": "OIDC is not configured", "details": None}},
        )
    try:
        meta = await fetch_oidc_metadata(row.oidc_issuer)
    except Exception as e:
        logger.exception("OIDC discovery failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "SSO_IDP_ERROR", "message": "Identity provider unreachable", "details": None}},
        ) from e
    meta = merge_oidc_endpoints(
        meta,
        {
            "authorization_endpoint": row.oidc_authorization_endpoint,
            "token_endpoint": row.oidc_token_endpoint,
            "jwks_uri": row.oidc_jwks_uri,
        },
    )
    state = create_sso_state_token(tenant_id=str(tenant_id), protocol="oidc")
    url = build_oidc_authorization_url(
        metadata=meta,
        client_id=row.oidc_client_id,
        redirect_uri=_oidc_redirect_uri(),
        state=state,
    )
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/auth/sso/oidc/callback")
async def oidc_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    if not settings.ENABLE_SSO:
        raise HTTPException(status_code=400, detail="SSO disabled")
    _rate_limit_sso(request)
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Missing code or state", "details": None}},
        )
    try:
        st = decode_sso_state_token(state)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Invalid state", "details": None}},
        ) from e
    tenant_id = uuid.UUID(st["tenant_id"])
    res = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == tenant_id,
            SsoProviderConfig.protocol == "oidc",
            SsoProviderConfig.is_enabled.is_(True),
        )
    )
    row = res.scalar_one_or_none()
    if row is None or not row.oidc_issuer or not row.oidc_client_id:
        raise HTTPException(status_code=400, detail="SSO not configured")
    client_secret = settings.OIDC_CLIENT_SECRET
    if not client_secret:
        logger.error("OIDC_CLIENT_SECRET not set — cannot complete token exchange")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "SSO_IDP_ERROR", "message": "Server SSO misconfiguration", "details": None}},
        )
    try:
        meta = await fetch_oidc_metadata(row.oidc_issuer)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "SSO_IDP_ERROR", "message": "Identity provider unreachable", "details": None}},
        ) from e
    meta = merge_oidc_endpoints(
        meta,
        {
            "authorization_endpoint": row.oidc_authorization_endpoint,
            "token_endpoint": row.oidc_token_endpoint,
            "jwks_uri": row.oidc_jwks_uri,
        },
    )
    try:
        token_payload = await exchange_oidc_code(
            token_endpoint=meta["token_endpoint"],
            client_id=row.oidc_client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=_oidc_redirect_uri(),
        )
    except Exception as e:
        logger.warning("OIDC token exchange failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Sign-in did not complete", "details": None}},
        ) from e
    id_token = token_payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="Missing id_token")
    try:
        claims = decode_oidc_id_token(
            id_token=id_token,
            jwks_uri=meta["jwks_uri"],
            client_id=row.oidc_client_id,
            issuer=meta.get("issuer") or row.oidc_issuer.rstrip("/"),
        )
    except Exception as e:
        logger.warning("id_token validation failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Sign-in did not complete", "details": None}},
        ) from e
    try:
        email, groups = extract_oidc_email_and_groups(claims)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Email claim missing from identity token", "details": None}},
        )
    sub = str(claims.get("sub") or "")
    issuer = str(claims.get("iss") or meta.get("issuer") or row.oidc_issuer)
    if not sub:
        raise HTTPException(status_code=400, detail="Invalid subject")
    try:
        user = await provision_or_login_federated_user(
            session,
            tenant_id=tenant_id,
            protocol="oidc",
            idp_issuer=issuer,
            idp_subject=sub,
            email=email,
            idp_groups=groups,
        )
    except FederatedLoginError as e:
        code = e.code
        if code == "SSO_DOMAIN_NOT_ALLOWED":
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "SSO_DOMAIN_NOT_ALLOWED", "message": "Email domain not approved", "details": None}},
            )
        if code == "SSO_INVITE_ONLY":
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "SSO_INVITE_ONLY", "message": "Invite-only mode — contact IT", "details": None}},
            )
        if code == "USER_INACTIVE":
            raise HTTPException(status_code=403, detail="Account inactive")
        raise
    token = create_access_token(subject=str(user.user_id), extra_claims={"tenant_id": str(user.tenant_id)})
    await session.commit()
    return _frontend_redirect_with_token(token)


@router.get("/auth/sso/saml/login")
async def saml_login(
    request: Request,
    tenant_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    if not settings.ENABLE_SSO:
        raise HTTPException(status_code=400, detail="SSO disabled")
    _rate_limit_sso(request)
    res = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == tenant_id,
            SsoProviderConfig.protocol == "saml",
            SsoProviderConfig.is_enabled.is_(True),
        )
    )
    row = res.scalar_one_or_none()
    if row is None or not row.saml_metadata_url:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "SSO_NOT_CONFIGURED", "message": "SAML is not configured", "details": None}},
        )
    try:
        md_xml = await fetch_saml_metadata_xml(row.saml_metadata_url)
        sso_url, idp_cert_pem = parse_idp_sso_url_and_cert(md_xml)
    except Exception as e:
        logger.exception("SAML metadata failed")
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "SSO_IDP_ERROR", "message": "Could not load SAML metadata", "details": None}},
        ) from e
    del idp_cert_pem  # used at ACS from fresh metadata fetch
    sp_entity = row.saml_entity_id or f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}/api/v1/auth/sso/saml/metadata"
    state = create_sso_state_token(tenant_id=str(tenant_id), protocol="saml")
    url = build_authn_request_redirect_url(
        idp_sso_url=sso_url,
        sp_entity_id=sp_entity,
        acs_url=_saml_acs_url(),
        relay_state=state,
    )
    return RedirectResponse(url=url, status_code=302)


@router.post("/auth/sso/saml/acs")
async def saml_acs(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    if not settings.ENABLE_SSO:
        raise HTTPException(status_code=400, detail="SSO disabled")
    _rate_limit_sso(request)
    form = await request.form()
    saml_response = form.get("SAMLResponse")
    relay_state = form.get("RelayState")
    if not saml_response or not relay_state:
        raise HTTPException(status_code=400, detail="Missing SAML payload")
    try:
        st = decode_sso_state_token(str(relay_state))
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid RelayState") from e
    tenant_id = uuid.UUID(st["tenant_id"])
    res = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == tenant_id,
            SsoProviderConfig.protocol == "saml",
            SsoProviderConfig.is_enabled.is_(True),
        )
    )
    row = res.scalar_one_or_none()
    if row is None or not row.saml_metadata_url:
        raise HTTPException(status_code=400, detail="SAML not configured")
    try:
        md_xml = await fetch_saml_metadata_xml(row.saml_metadata_url)
        _, idp_cert_pem = parse_idp_sso_url_and_cert(md_xml)
        issuer, name_id, email = decode_saml_post(str(saml_response), idp_cert_pem)
    except Exception as e:
        logger.warning("SAML ACS parse failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Sign-in did not complete", "details": None}},
        ) from e
    if not email:
        if "@" in name_id:
            email = name_id.lower()
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "VALIDATION_ERROR", "message": "Email not found in SAML assertion", "details": None}},
            )
    try:
        user = await provision_or_login_federated_user(
            session,
            tenant_id=tenant_id,
            protocol="saml",
            idp_issuer=issuer,
            idp_subject=name_id,
            email=email,
            idp_groups=None,
        )
    except FederatedLoginError as e:
        if e.code == "SSO_DOMAIN_NOT_ALLOWED":
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "SSO_DOMAIN_NOT_ALLOWED", "message": "Email domain not approved", "details": None}},
            )
        if e.code == "SSO_INVITE_ONLY":
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "SSO_INVITE_ONLY", "message": "Invite-only mode", "details": None}},
            )
        if e.code == "USER_INACTIVE":
            raise HTTPException(status_code=403, detail="Account inactive")
        raise
    token = create_access_token(subject=str(user.user_id), extra_claims={"tenant_id": str(user.tenant_id)})
    await session.commit()
    return _frontend_redirect_with_token(token)


@router.get("/auth/sso/saml/metadata")
async def saml_sp_metadata(
    tenant_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db),
) -> Response:
    res = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == tenant_id,
            SsoProviderConfig.protocol == "saml",
        )
    )
    row = res.scalar_one_or_none()
    settings = get_settings()
    entity = (
        row.saml_entity_id if row and row.saml_entity_id else f"{settings.PUBLIC_API_BASE_URL}/api/v1/auth/sso/saml/metadata"
    )
    xml = build_sp_metadata_xml(entity_id=entity, acs_url=_saml_acs_url())
    return Response(content=xml, media_type="application/xml")


# --- Tenant SSO admin (authenticated) ---


class OidcConfigBlock(BaseModel):
    sso_provider_id: uuid.UUID | None = None
    is_enabled: bool = False
    display_name: str | None = None
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_authorization_endpoint: str | None = None
    oidc_token_endpoint: str | None = None
    oidc_jwks_uri: str | None = None


class SamlConfigBlock(BaseModel):
    sso_provider_id: uuid.UUID | None = None
    is_enabled: bool = False
    display_name: str | None = None
    saml_entity_id: str | None = None
    saml_metadata_url: str | None = None
    saml_acs_url_path: str | None = None


class TenantSsoConfigurationOut(BaseModel):
    tenant_id: uuid.UUID
    oidc: OidcConfigBlock | None
    saml: SamlConfigBlock | None
    oidc_redirect_uri_readonly: str
    saml_acs_url_readonly: str


class SsoConfigurationPut(BaseModel):
    protocol: str = Field(pattern="^(oidc|saml)$")
    is_enabled: bool = False
    display_name: str | None = None
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_authorization_endpoint: str | None = None
    oidc_token_endpoint: str | None = None
    oidc_jwks_uri: str | None = None
    saml_entity_id: str | None = None
    saml_metadata_url: str | None = None
    saml_acs_url_path: str | None = None


def _bundle_sso_response(user_tenant_id: uuid.UUID, oidc_row: SsoProviderConfig | None, saml_row: SsoProviderConfig | None) -> TenantSsoConfigurationOut:
    settings = get_settings()
    oidc_block = None
    if oidc_row is not None:
        oidc_block = OidcConfigBlock(
            sso_provider_id=oidc_row.sso_provider_id,
            is_enabled=oidc_row.is_enabled,
            display_name=oidc_row.display_name,
            oidc_issuer=oidc_row.oidc_issuer,
            oidc_client_id=oidc_row.oidc_client_id,
            oidc_authorization_endpoint=oidc_row.oidc_authorization_endpoint,
            oidc_token_endpoint=oidc_row.oidc_token_endpoint,
            oidc_jwks_uri=oidc_row.oidc_jwks_uri,
        )
    saml_block = None
    if saml_row is not None:
        saml_block = SamlConfigBlock(
            sso_provider_id=saml_row.sso_provider_id,
            is_enabled=saml_row.is_enabled,
            display_name=saml_row.display_name,
            saml_entity_id=saml_row.saml_entity_id,
            saml_metadata_url=saml_row.saml_metadata_url,
            saml_acs_url_path=saml_row.saml_acs_url_path,
        )
    return TenantSsoConfigurationOut(
        tenant_id=user_tenant_id,
        oidc=oidc_block,
        saml=saml_block,
        oidc_redirect_uri_readonly=f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}/api/v1/auth/sso/oidc/callback",
        saml_acs_url_readonly=f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}/api/v1/auth/sso/saml/acs",
    )


@router.get("/tenant/sso/configuration", response_model=TenantSsoConfigurationOut)
async def get_sso_configuration(
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> TenantSsoConfigurationOut:
    res = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == user.tenant_id,
            SsoProviderConfig.protocol == "oidc",
        )
    )
    oidc_row = res.scalar_one_or_none()
    res2 = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == user.tenant_id,
            SsoProviderConfig.protocol == "saml",
        )
    )
    saml_row = res2.scalar_one_or_none()
    return _bundle_sso_response(user.tenant_id, oidc_row, saml_row)


@router.put("/tenant/sso/configuration", response_model=TenantSsoConfigurationOut)
async def put_sso_configuration(
    body: SsoConfigurationPut,
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> TenantSsoConfigurationOut:
    res = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == user.tenant_id,
            SsoProviderConfig.protocol == body.protocol,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = SsoProviderConfig(tenant_id=user.tenant_id, protocol=body.protocol)
        session.add(row)
    row.is_enabled = body.is_enabled
    row.display_name = body.display_name
    if body.protocol == "oidc":
        row.oidc_issuer = body.oidc_issuer
        row.oidc_client_id = body.oidc_client_id
        row.oidc_authorization_endpoint = body.oidc_authorization_endpoint
        row.oidc_token_endpoint = body.oidc_token_endpoint
        row.oidc_jwks_uri = body.oidc_jwks_uri
    else:
        row.saml_entity_id = body.saml_entity_id
        row.saml_metadata_url = body.saml_metadata_url
        row.saml_acs_url_path = body.saml_acs_url_path
    await session.commit()
    await session.refresh(row)
    res_o = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == user.tenant_id,
            SsoProviderConfig.protocol == "oidc",
        )
    )
    res_s = await session.execute(
        select(SsoProviderConfig).where(
            SsoProviderConfig.tenant_id == user.tenant_id,
            SsoProviderConfig.protocol == "saml",
        )
    )
    return _bundle_sso_response(user.tenant_id, res_o.scalar_one_or_none(), res_s.scalar_one_or_none())


class AllowlistItem(BaseModel):
    allowlist_id: uuid.UUID
    email_domain: str
    created_at: Any


class AllowlistOut(BaseModel):
    items: list[AllowlistItem]


class AllowlistPost(BaseModel):
    email_domain: str = Field(min_length=1, max_length=255)


@router.get("/tenant/sso/domain-allowlist", response_model=AllowlistOut)
async def get_domain_allowlist(
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> AllowlistOut:
    res = await session.execute(
        select(TenantEmailDomainAllowlist).where(TenantEmailDomainAllowlist.tenant_id == user.tenant_id)
    )
    rows = res.scalars().all()
    return AllowlistOut(
        items=[
            AllowlistItem(allowlist_id=r.allowlist_id, email_domain=r.email_domain, created_at=r.created_at)
            for r in rows
        ]
    )


@router.post("/tenant/sso/domain-allowlist", response_model=AllowlistItem, status_code=201)
async def post_domain_allowlist(
    body: AllowlistPost,
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> AllowlistItem:
    domain = body.email_domain.strip().lower().lstrip("@")
    row = TenantEmailDomainAllowlist(
        tenant_id=user.tenant_id,
        email_domain=domain,
        created_by_user_id=user.user_id,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Duplicate domain") from None
    await session.refresh(row)
    return AllowlistItem(allowlist_id=row.allowlist_id, email_domain=row.email_domain, created_at=row.created_at)


@router.delete("/tenant/sso/domain-allowlist/{allowlist_id}", status_code=204)
async def delete_domain_allowlist(
    allowlist_id: uuid.UUID,
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await session.execute(
        delete(TenantEmailDomainAllowlist).where(
            TenantEmailDomainAllowlist.allowlist_id == allowlist_id,
            TenantEmailDomainAllowlist.tenant_id == user.tenant_id,
        )
    )
    await session.commit()
    return Response(status_code=204)


class GroupMappingOut(BaseModel):
    mapping_id: uuid.UUID
    idp_group_identifier: str
    app_role: str
    org_id: uuid.UUID


class GroupMappingPost(BaseModel):
    idp_group_identifier: str
    app_role: str
    org_id: uuid.UUID


class GroupMappingPatch(BaseModel):
    idp_group_identifier: str | None = None
    app_role: str | None = None
    org_id: uuid.UUID | None = None


@router.get("/tenant/sso/group-role-mappings", response_model=list[GroupMappingOut])
async def list_group_mappings(
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> list[GroupMappingOut]:
    res = await session.execute(
        select(IdpGroupRoleMapping).where(IdpGroupRoleMapping.tenant_id == user.tenant_id)
    )
    return [
        GroupMappingOut(
            mapping_id=r.mapping_id,
            idp_group_identifier=r.idp_group_identifier,
            app_role=r.app_role,
            org_id=r.org_id,
        )
        for r in res.scalars().all()
    ]


@router.post("/tenant/sso/group-role-mappings", response_model=GroupMappingOut, status_code=201)
async def create_group_mapping(
    body: GroupMappingPost,
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> GroupMappingOut:
    row = IdpGroupRoleMapping(
        tenant_id=user.tenant_id,
        idp_group_identifier=body.idp_group_identifier,
        app_role=body.app_role,
        org_id=body.org_id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return GroupMappingOut(
        mapping_id=row.mapping_id,
        idp_group_identifier=row.idp_group_identifier,
        app_role=row.app_role,
        org_id=row.org_id,
    )


@router.patch("/tenant/sso/group-role-mappings/{mapping_id}", response_model=GroupMappingOut)
async def patch_group_mapping(
    mapping_id: uuid.UUID,
    body: GroupMappingPatch,
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> GroupMappingOut:
    res = await session.execute(
        select(IdpGroupRoleMapping).where(
            IdpGroupRoleMapping.mapping_id == mapping_id,
            IdpGroupRoleMapping.tenant_id == user.tenant_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if body.idp_group_identifier is not None:
        row.idp_group_identifier = body.idp_group_identifier
    if body.app_role is not None:
        row.app_role = body.app_role
    if body.org_id is not None:
        row.org_id = body.org_id
    await session.commit()
    await session.refresh(row)
    return GroupMappingOut(
        mapping_id=row.mapping_id,
        idp_group_identifier=row.idp_group_identifier,
        app_role=row.app_role,
        org_id=row.org_id,
    )


@router.delete("/tenant/sso/group-role-mappings/{mapping_id}", status_code=204)
async def delete_group_mapping(
    mapping_id: uuid.UUID,
    user: User = Depends(require_tenant_sso_admin),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await session.execute(
        delete(IdpGroupRoleMapping).where(
            IdpGroupRoleMapping.mapping_id == mapping_id,
            IdpGroupRoleMapping.tenant_id == user.tenant_id,
        )
    )
    await session.commit()
    return Response(status_code=204)
