# Phase 6 validation and QA sign-off

| Field | Value |
|--------|--------|
| **Document file** | `docs/qa/phase-6-report.md` (this file) |
| **Aligned to** | [`docs/requirements/phase-6-requirements.md`](../requirements/phase-6-requirements.md), [`.cursor/rules/quality-analyst.mdc`](../../.cursor/rules/quality-analyst.mdc) |
| **Last validated** | **6 April 2026** |
| **Legend** | `[x]` Done · `[ ]` Not done · `N/A` Out of scope per PRD |

---

## Executive recommendation

| Verdict | **GO** (Phase 6 — enterprise identity & governance; backend-heavy automation) |
|---------|--------------------------------------------------------------------------------|
| **Rationale** | **Full suite:** **127 passed**, **0 skipped** (~40–70s depending on cold Alembic). **Phase 1–5 regression** remains green (analytics, ingest, NL query, revenue, smoke, HubSpot, Phase 5 flags + metrics). **Phase 6** is covered by **27** automated integration tests in [`tests/integration/test_phase6_integration.py`](../../backend/tests/integration/test_phase6_integration.py). **Frontend** `npm run build` **succeeds** (governance route behind `VITE_ENABLE_PHASE6`). |
| **Tooling note** | Same as Phase 5: integration tests require **`pytest-asyncio` ≥ 0.24** with session-scoped asyncio loop (see `backend/pyproject.toml`). |
| **Residual risk** | **End-to-end OIDC/SAML** with a **real IdP** (discovery, token exchange, SAML ACS) is **not** exercised in CI — tests cover **configuration APIs**, **federation/JIT** logic, **safe HTTP errors**, and **governance** endpoints. **Finance freeze windows** are **documentation / copy** per PRD (optional in-product enforcement) — **not** asserted in automation. |
| **Release debt** | Consider **contract tests** or **recorded mocks** for OIDC discovery + token endpoint if pilots require deterministic CI proof of full redirect flows. |

---

## 1. Requirements source

- **Primary:** [`phase-6-requirements.md`](../requirements/phase-6-requirements.md) — Stories **6.1** (SSO), **6.2** (audit export & retention), **6.3** (enterprise admin), **6.4** (operational visibility).

---

## 2. Automation executed

```bash
cd backend && pytest tests/ -v --tb=short
```

**Result:** **127 passed**, **0 skipped**. Integration sessions **auto-migrate** to head per [`tests/conftest.py`](../../backend/tests/conftest.py) when integration tests are collected (unless `PYTEST_SKIP_ALEMBIC_UPGRADE` is set).

**Phase 6 tests:**

- [`tests/integration/test_phase6_integration.py`](../../backend/tests/integration/test_phase6_integration.py)

**Frontend:**

```bash
cd frontend && npm run build
```

**Result:** **Success** (TypeScript + Vite production build).

---

## 3. Phase 1–5 regression (shared components)

| Area | Evidence |
|------|----------|
| Validator, golden aggregate, overlap, large validate, semantic bundle (Phase 3/5) | Unit tests — **pass** |
| Revenue API auth / org scope | `test_revenue_api.py` — **pass** |
| Analytics Stories 2.1–2.4 + auth | `test_analytics_api.py` — **pass** |
| Ingest E2E, loader, soft-delete, uniqueness, ingest auth | Integration tests — **pass** |
| NL query Stories 3.1–3.4 | `test_nl_query_api.py` — **pass** |
| HubSpot Phase 4 | `test_hubspot_phase4.py`, `test_hubspot_oauth_scopes.py` — **pass** |
| Health, `/auth/me`, batch 404 | `test_api_smoke.py` — **pass** |
| Phase 5 flags + enterprise metrics | `test_phase5_integration.py`, `test_phase5_flags.py`, `test_semantic_layer_bundle.py` — **pass** |

---

## 4. Phase 6 acceptance criteria → tests

### Story 6.1 — Enterprise SSO (SAML 2.0 / OIDC)

| Acceptance criterion | Automated test | Status |
|----------------------|------------------|--------|
| **IdP configuration** stored via admin (issuer, client id, metadata URL path); **no** client secret in API payloads | `test_story_6_1_put_sso_configuration_stores_oidc_and_no_secret_field` | `[x]` |
| **Domain allowlist** admin API | `test_story_6_1_domain_allowlist_api_round_trip` | `[x]` |
| **JIT** with allowlist; **invite-only** blocks JIT; **domain** not allowlisted blocks | `test_story_6_1_jit_provision_with_domain_allowlist`; `test_story_6_1_invite_only_blocks_jit`; `test_story_6_1_domain_not_on_allowlist_blocks` | `[x]` |
| **Optional IdP group → app role** via explicit mapping | `test_story_6_1_explicit_group_mapping_applies_app_role` | `[x]` |
| **Break-glass** password: standard SSO user blocked; **admin** allowed when policy requires SSO | `test_story_6_1_password_login_blocked_when_sso_required_for_saml_user`; `test_story_6_1_break_glass_admin_password_allowed_when_sso_required` | `[x]` |
| **`/auth/me`** exposes **`primary_auth`** / **`sso_required_for_user`** | `test_auth_me_includes_primary_auth`; `test_story_6_1_sso_required_for_user_on_me_when_policy_enabled` | `[x]` |
| **SSO gated** when globally disabled; **OIDC login** returns structured error | `test_story_6_1_oidc_login_400_when_sso_disabled` | `[x]` |
| **IT Admin** (and not viewer) for SSO admin APIs | `test_story_6_1_tenant_sso_admin_endpoints_forbid_viewer` | `[x]` |
| **Failure modes** — missing callback params, **no stack trace** in JSON | `test_story_6_1_oidc_callback_missing_code_returns_safe_error` | `[x]` |
| Full **OIDC redirect + token exchange + JWKS** against live IdP | **Not** in suite (would need network/mocks) | `N/A` CI |
| Full **SAML ACS** with signed assertion | **Not** in suite | `N/A` CI |

### Story 6.2 — Audit export and retention alignment

| Acceptance criterion | Automated test | Status |
|----------------------|------------------|--------|
| **Export scope** — families: ingestion, nl_query, hubspot_sync, sso_security | `test_story_6_2_audit_export_jsonl_and_all_event_families` | `[x]` |
| **CSV / JSON Lines** formats | `test_audit_export_csv`; `test_story_6_2_audit_export_jsonl_and_all_event_families` | `[x]` |
| **`audit_export`** permission; **403** without | `test_story_6_2_audit_export_forbidden_without_permission` | `[x]` |
| **Export action logged** (`audit_export.completed`) | `test_story_6_2_audit_export_logs_completed_action` | `[x]` |
| **User id + email** in export rows (accountability) | `test_story_6_2_export_rows_include_user_email_for_accountability` | `[x]` |
| **Validation** — invalid date order **422**; range **> 400 days** **413** | `test_story_6_2_audit_export_invalid_date_range_422`; `test_story_6_2_audit_export_range_too_large_413` | `[x]` |
| **Retention** surfaced on tenant security (default notice) | `test_tenant_security_get`; `test_story_6_3_reporting_currency_visible_on_tenant_security` (same payload includes `retention_notice_label`) | `[x]` |
| **Tamper-evidence** / append-only semantics | **DB design** — no automated mutation test | `N/A` |

### Story 6.3 — Enterprise admin — security posture

| Acceptance criterion | Automated test | Status |
|----------------------|------------------|--------|
| **Admin-only** — viewer **403** on `/tenant/security` | `test_story_6_3_viewer_cannot_read_tenant_security` | `[x]` |
| **Security patch audited** | `test_story_6_3_patch_tenant_security_writes_audit_event` | `[x]` |
| **Reporting currency** visibility | `test_story_6_3_reporting_currency_visible_on_tenant_security` | `[x]` |
| **Documentation** — Finance freeze windows | **Copy / docs** per PRD — not API-testable | `N/A` |

### Story 6.4 — Operational visibility

| Acceptance criterion | Automated test | Status |
|----------------------|------------------|--------|
| **HubSpot** — connection + last sync; **partial failure** not silent green | `test_story_6_4_operations_summary_surfaces_hubspot_partial_failure` | `[x]` |
| **Background / ingestion** failures surfaced | `test_story_6_4_operations_summary_includes_failed_batch_stub` | `[x]` |
| **Consolidated summary** shape | `test_operations_summary` | `[x]` |

---

## 5. Regression — Tech Lead touchpoints (Phase 6)

| Component | Verification |
|-----------|--------------|
| `app/main.py` — `phase6_sso_router`, `phase6_governance_router` | Full suite — **pass** |
| `app/core/deps.py` — `require_tenant_sso_admin`, `require_audit_export_permission` | Phase 6 + existing routes — **pass** |
| `app/api/v1/auth.py` — login SSO gate, `/me` SSO fields | Phase 6 login + `/me` tests — **pass** |
| `app/api/v1/phase6_sso.py`, `phase6_governance.py` | Phase 6 integration tests — **pass** |
| `app/services/identity/federation.py` | JIT / invite / domain / group mapping tests — **pass** |
| `app/services/audit_export_service.py`, `admin_operations_service.py` | Export + operations tests — **pass** |
| Phase 1–5 unchanged behavior | Full regression — **pass** |

---

## 6. Known gaps

| Gap | Severity | Notes |
|-----|----------|--------|
| **Live IdP** OIDC/SAML round-trip | Medium (pilot-specific) | Add mocked HTTP or staging IdP tests if contract requires |
| **Rate limiting** on SSO endpoints | Low | Code path exists; burst **429** not matrix-tested |
| **Finance freeze** in-product | N/A | Explicitly optional / docs per PRD |

---

## 7. Sign-off

| Role | Status |
|------|--------|
| **Quality Analyst (automation)** | **GO** for Phase 6 backend acceptance coverage; Phase 1–5 regression **pass**; frontend **build** **pass**. |

---

*Aligned to [`product-requirements.md`](../requirements/product-requirements.md). UX alignment with `@ux-ui-designer`; schema with `@technical-architect`.*

**Revision history:**

| Date | Change |
|------|--------|
| 6 April 2026 | Initial Phase 6 QA report: 127 tests green; AC matrix; GO; IdP E2E noted as residual risk. |
