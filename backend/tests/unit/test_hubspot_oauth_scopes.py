"""Phase 4 Story 4.1 — OAuth URL uses settings; least-privilege scopes (not hardcoded secrets)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.integrations.hubspot.constants import DEFAULT_SCOPES
from app.services.integrations.hubspot.oauth_authorize import build_authorization_url


def test_story_4_1_default_scopes_are_least_privilege_deals_and_companies() -> None:
    """Parent PRD §5 — Deals primary; scopes limited to oauth + CRM read for deals and companies."""
    assert "crm.objects.deals.read" in DEFAULT_SCOPES
    assert "crm.objects.companies.read" in DEFAULT_SCOPES
    assert "crm.objects.deals.write" not in DEFAULT_SCOPES


def test_story_4_1_build_authorization_url_uses_settings_client_id_not_hardcoded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credentials come from environment/settings, not literals in the authorize URL builder."""
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "env-client-id-unique-12345")
    monkeypatch.setenv("HUBSPOT_REDIRECT_URI", "https://api.example.com/oauth/callback")
    get_settings.cache_clear()
    try:
        url = build_authorization_url(state="csrf-state-xyz")
    finally:
        get_settings.cache_clear()
    assert "env-client-id-unique-12345" in url
    assert "csrf-state-xyz" in url
    assert "scope=" in url
    assert DEFAULT_SCOPES.split()[0] in url or "oauth" in url
