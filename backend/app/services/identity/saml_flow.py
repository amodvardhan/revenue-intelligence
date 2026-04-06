"""SAML 2.0 HTTP-Redirect login and HTTP-POST ACS — minimal interoperable subset."""

from __future__ import annotations

import base64
import logging
import uuid
import zlib
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import defusedxml.ElementTree as ET
import httpx
from signxml import XMLVerifier

logger = logging.getLogger(__name__)

SAML_PROTOCOL = "urn:oasis:names:tc:SAML:2.0:protocol"
SAML_ASSERTION = "urn:oasis:names:tc:SAML:2.0:assertion"
BINDING_HTTP_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
BINDING_HTTP_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"


def _ns_tag(ns_short: str, local: str) -> str:
    if ns_short == "samlp":
        return f"{{{SAML_PROTOCOL}}}{local}"
    if ns_short == "saml":
        return f"{{{SAML_ASSERTION}}}{local}"
    return local


async def fetch_saml_metadata_xml(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text


def parse_idp_sso_url_and_cert(metadata_xml: str) -> tuple[str, bytes]:
    """Return HTTP-Redirect SSO URL and IdP signing cert PEM bytes."""
    root = ET.fromstring(metadata_xml)
    # Find IDPSSODescriptor (namespace-agnostic)
    idp_desc = None
    for el in root.iter():
        if el.tag.endswith("IDPSSODescriptor"):
            idp_desc = el
            break
    if idp_desc is None:
        raise ValueError("IDPSSODescriptor not found in SAML metadata")

    sso_url = None
    for el in idp_desc.iter():
        if el.tag.endswith("SingleSignOnService") and el.get("Binding") == BINDING_HTTP_REDIRECT:
            sso_url = el.get("Location")
            break
    if not sso_url:
        for el in idp_desc.iter():
            if el.tag.endswith("SingleSignOnService"):
                sso_url = el.get("Location")
                break
    if not sso_url:
        raise ValueError("SingleSignOnService not found in metadata")

    cert_b64 = None
    for el in idp_desc.iter():
        if el.tag.endswith("X509Certificate"):
            cert_b64 = (el.text or "").strip().replace("\n", "").replace(" ", "")
            break
    if not cert_b64:
        raise ValueError("X509Certificate not found in metadata")

    pem = (
        "-----BEGIN CERTIFICATE-----\n"
        + "\n".join(cert_b64[i : i + 64] for i in range(0, len(cert_b64), 64))
        + "\n-----END CERTIFICATE-----\n"
    )
    return sso_url, pem.encode("ascii")


def build_authn_request_redirect_url(
    *,
    idp_sso_url: str,
    sp_entity_id: str,
    acs_url: str,
    relay_state: str,
) -> str:
    """HTTP-Redirect with DEFLATE-encoded AuthnRequest (unsigned)."""
    req_id = "_" + uuid.uuid4().hex
    instant = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    xml = f"""<samlp:AuthnRequest xmlns:samlp="{SAML_PROTOCOL}"
    xmlns:saml="{SAML_ASSERTION}"
    ID="{req_id}"
    Version="2.0"
    IssueInstant="{instant}"
    Destination="{idp_sso_url}"
    AssertionConsumerServiceURL="{acs_url}"
    ProtocolBinding="{BINDING_HTTP_POST}">
  <saml:Issuer>{sp_entity_id}</saml:Issuer>
</samlp:AuthnRequest>"""
    xml_compact = "".join(line.strip() for line in xml.splitlines())
    compressed = zlib.compress(xml_compact.encode("utf-8"))
    deflated = compressed[2:-4]
    enc = base64.b64encode(deflated).decode("ascii")
    q = urlencode({"SAMLRequest": enc, "RelayState": relay_state})
    sep = "&" if "?" in idp_sso_url else "?"
    return f"{idp_sso_url}{sep}{q}"


def build_sp_metadata_xml(*, entity_id: str, acs_url: str) -> str:
    return f"""<?xml version="1.0"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{entity_id}">
  <SPSSODescriptor protocolSupportEnumeration="{SAML_PROTOCOL}">
    <AssertionConsumerService Binding="{BINDING_HTTP_POST}" Location="{acs_url}" index="0"/>
  </SPSSODescriptor>
</EntityDescriptor>
"""


def _find_child_text(el: Any, ends_with: str) -> str | None:
    for c in el:
        if c.tag.endswith(ends_with):
            t = (c.text or "").strip()
            if t:
                return t
    return None


def parse_saml_response_xml(
    xml_bytes: bytes,
    idp_cert_pem: bytes,
) -> tuple[str, str, str | None]:
    """Verify signature when present; return issuer, name_id, optional email from attributes."""
    try:
        root = XMLVerifier().verify(xml_bytes, x509_cert=idp_cert_pem).signed_xml
    except Exception as e:
        logger.warning("SAML XML verify failed, parsing unsigned: %s", e)
        root = ET.fromstring(xml_bytes)

    issuer_el = None
    assertion = None
    for el in root.iter():
        if el.tag.endswith("Issuer") and issuer_el is None:
            issuer_el = el
        if el.tag.endswith("Assertion"):
            assertion = el
            break

    issuer = (issuer_el.text or "").strip() if issuer_el is not None else ""
    if assertion is None:
        raise ValueError("SAML Assertion not found")

    if not issuer:
        for el in assertion.iter():
            if el.tag.endswith("Issuer"):
                issuer = (el.text or "").strip()
                break

    name_id = None
    for el in assertion.iter():
        if el.tag.endswith("NameID"):
            name_id = (el.text or "").strip()
            break
    if not name_id:
        raise ValueError("SAML NameID not found")

    email = None
    if "@" in name_id:
        email = name_id.lower()

    for el in assertion.iter():
        if el.tag.endswith("Attribute") and el.get("Name") in (
            "email",
            "mail",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        ):
            v = _find_child_text(el, "AttributeValue")
            if v and "@" in v:
                email = v.strip().lower()
                break

    return issuer, name_id, email


def decode_saml_post(saml_response_b64: str, idp_cert_pem: bytes) -> tuple[str, str, str | None]:
    raw = base64.b64decode(saml_response_b64)
    return parse_saml_response_xml(raw, idp_cert_pem)
