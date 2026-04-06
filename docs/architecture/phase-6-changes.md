# Phase 6 Architecture Delta (vs Phase 5)

**Status:** APPROVED (architecture alignment)  
**Aligned to:** [`docs/requirements/phase-6-requirements.md`](../requirements/phase-6-requirements.md) (Product Owner approval **6 April 2026** — requirements **LOCKED**)  
**Purpose:** Single place listing **what Phase 6 adds** versus **what already exists** from Phase 5, **open architect decisions** from the requirements doc, and **risks to Phase 5 (and earlier phases)**.

---

## 1. Already exists (Phase 5 — unchanged baseline)

| Area | What exists |
|------|-------------|
| **Forecast / cost / FX / segments** | `forecast_series`, `fact_forecast`, `fact_cost`, `cost_allocation_rule`, `segment_definition`, `segment_membership`, `fx_rate`; APIs under `api-contracts.md` §10 |
| **Reporting currency** | `tenants.default_currency_code`; `GET /tenant/settings`, consolidated analytics — Phase 6 **surfaces** visibility only (Story 6.3 / approved decision 8) |
| **NL + semantic layer** | `query_audit_log`, governed measures — **no** new NL capabilities in Phase 6 |
| **HubSpot** | `hubspot_connection`, `integration_sync_run`, sync and status APIs — Phase 6 **aggregates** operational views (Story 6.4) |
| **Audit (append-only)** | `ingestion_batch`, `query_audit_log`, `audit_event`, integration sync runs — **sources** for **export** (Story 6.2) |
| **Auth (baseline)** | `POST /auth/login`, JWT, `users` + `user_org_role`, RLS session vars |

Phase 5 **did not** ship enterprise **SSO**, **federated identity**, **audit export** APIs, **fine-grained** `audit_export` permission, or **consolidated admin operations** dashboard beyond existing HubSpot/sync listings.

---

## 2. New in Phase 6 (schema)

| Object | Purpose |
|--------|---------|
| **`sso_provider_config`** | Per-tenant **OIDC** and/or **SAML 2.0** binding — **non-secret** metadata only; **UNIQUE (tenant_id, protocol)** |
| **`tenant_email_domain_allowlist`** | **JIT** email domain allowlist (Story 6.1) |
| **`user_federated_identity`** | Stable **IdP issuer + subject** ↔ `users` link; idempotent JIT |
| **`idp_group_role_mapping`** | **Optional** explicit IdP group identifier → `user_org_role`-style role **per org** |
| **`user_permission`** | Fine-grained codes — e.g. **`audit_export`** (approved product decision 6) |
| **`tenant_security_settings`** | **1:1** with tenant: `invite_only`, `require_sso_for_standard_users`, session timeouts, retention **notice** label |
| **`users.primary_auth`** | `local` · `oidc` · `saml` — how the user normally signs in |

**Reuse:** **`audit_event`** (recommended) for **SSO** and **audit_export** completion events — append-only; **no** silent edits to historical `query_audit_log` / `ingestion_batch` rows.

---

## 3. New in Phase 6 (services & modules)

| Piece | Role |
|-------|------|
| **`services/identity/`** | OIDC/SAML login/callback flows, token/assertion validation, JIT user creation, **user_federated_identity** persistence, mapping optional IdP groups → roles |
| **`core/security.py` (extend)** | Integrate IdP validation with existing JWT issuance; **no** hardcoded IdP secrets |
| **`core/config.py` (extend)** | SSO-related URLs, rate limits, export caps — **document** in `.env.example` |
| **Repositories** | Read models for cross-table **audit export**; **paginated** queries with **time bounds** |
| **Integrations / tasks (read-only aggregation)** | **`/admin/operations/summary`** reuses **HubSpot** + **Celery** / batch status — **no duplicate** business logic with inconsistent semantics |

---

## 4. New in Phase 6 (HTTP API)

All under `/api/v1` — see `api-contracts.md` §11.

| Method | Path | Stories |
|--------|------|---------|
| `GET` | `/auth/sso/oidc/login` | 6.1 |
| `GET` | `/auth/sso/oidc/callback` | 6.1 |
| `GET` | `/auth/sso/saml/login` | 6.1 |
| `POST` | `/auth/sso/saml/acs` | 6.1 |
| `GET` | `/auth/sso/saml/metadata` | 6.1 |
| `GET` | `/tenant/sso/configuration` | 6.1, 6.3 |
| `PUT` | `/tenant/sso/configuration` | 6.1, 6.3 |
| `GET` | `/tenant/sso/domain-allowlist` | 6.1 |
| `POST` | `/tenant/sso/domain-allowlist` | 6.1 |
| `DELETE` | `/tenant/sso/domain-allowlist/{allowlist_id}` | 6.1 |
| `GET` | `/tenant/sso/group-role-mappings` | 6.1 |
| `POST` | `/tenant/sso/group-role-mappings` | 6.1 |
| `PATCH` | `/tenant/sso/group-role-mappings/{mapping_id}` | 6.1 |
| `DELETE` | `/tenant/sso/group-role-mappings/{mapping_id}` | 6.1 |
| `GET` | `/tenant/security` | 6.3 |
| `PATCH` | `/tenant/security` | 6.3 |
| `POST` | `/audit/exports` | 6.2 |
| `GET` | `/audit/exports/{export_job_id}` | 6.2 (if async exports) |
| `GET` | `/admin/operations/summary` | 6.4 |
| `GET` | `/admin/operations/background-jobs` | 6.4 (optional) |

**Optional:** extend **`GET /me`** with `primary_auth` / `sso_required_for_user` — see §11.

---

## 5. Explicitly out of scope (Phase 6 requirements)

Per [`phase-6-requirements.md`](../requirements/phase-6-requirements.md):

- **Multi-tenant SaaS** productization; **full SCIM** lifecycle (JIT + allowlist is in scope).  
- **New** revenue analytics, **new** NL capabilities, **new** CRM connectors, **new** Phase 5 metric types.  
- **Automated SIEM streaming** / outbound webhooks (manual export satisfies Story 6.2).  
- **In-product legal certification** (GDPR, SOC 2).  
- **Calendar enforcement** for Finance freeze windows — **optional**; **out of scope** if not listed in requirements.

---

## 6. Open architect decisions (from Phase 6 requirements)

Resolved in design review before implementation freeze (see requirements §“Decisions that need architect input”):

1. **Libraries and bindings** — OIDC/SAML packages; callback URLs; SAML metadata fetch/cache; first-pilot **SAML** profile if SAML-first reorder applies.  
2. **Identity linking** — JIT row creation; **stable key** (`idp_issuer` + `idp_subject`); **email change** and **account merge** behavior; **invite-only** interaction.  
3. **Token and session model** — Map OIDC/SAML to existing **JWT** shape; **refresh**, **logout**, **front-channel / back-channel** logout; single logout expectations.  
4. **Secrets and rotation** — Where IdP secrets and SAML certs live; **rotation** without full redeploy.  
5. **Audit volume** — Whether **SSO events** use **`audit_event`** only or a **dedicated** append-only table; **indexing** for 365-day export queries.  
6. **RLS and SSO** — Tenant and org/BU scoping when principal is established via **IdP** vs **`users`** row (defense-in-depth).  
7. **Deployment topology** — Per-tenant SSO config in DB vs env-only for dedicated deployments; CI/CD secrets.  
8. **Rate limiting** — SSO callbacks and **`audit/exports`** — throttling, **max export rows**, **DoS** protection.

---

## 7. Phase 5 regression / breakage risks

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| **Stricter login** | Enabling **`require_sso_for_standard_users`** **blocks** password login for normal users — can lock out if IdP misconfigured. | **Break-glass** Super Admin path; staged rollout; feature flags (`ENABLE_SSO`); clear IT runbooks. |
| **JIT / allowlist** | Wrong domain list **denies** legitimate users; empty list + JIT **can** block all SSO users. | Admin UX + validation; **invite-only** mode documented; audit on first login. |
| **IdP group → role mapping** | Incorrect mapping **elevates** or **strips** access vs **`user_org_role`**. | **Explicit** rows only; **application roles authoritative**; audit mapping changes; **no** remove-all on each login unless product says so. |
| **RLS session variables** | If SSO path **sets** `app.tenant_id` / `app.user_id` incorrectly, **Phase 5** facts (FX, segments, forecast) **leak** or **empty** incorrectly. | Single auth dependency that sets RLS vars from **`users`** after federated link; integration tests for SSO + `GET /revenue` / `GET /forecast/facts`. |
| **Audit export load** | Large exports over **`query_audit_log`** + **`ingestion_batch`** + sync tables can **impact** production DB **read** performance. | **Async** job + **read replica** (if available), **strict** windows, **rate limits**, **off-peak** guidance in runbooks. |
| **`users` schema migration** | Adding **`primary_auth`** with default **`local`** — ensure **backfill** for existing rows; **nullable** `password_hash` semantics for SSO-only users. | Alembic migration + application checks; Super Admin retains password per policy. |
| **`tenant_security_settings`** | Missing row vs **defaults** — inconsistent behavior for `invite_only`. | Lazy-create on first admin save **or** migration seed **one** row per tenant with defaults. |
| **Phase 5 feature flags** | **`ENABLE_PHASE5`** off must **still** allow Phase 6 governance on **core** tables **without** requiring forecast/segment routes. | Phase 6 **does not** depend on Phase 5 **routes** for SSO; **avoid** importing Phase 5-only services from SSO **login** path. |
| **Consolidated operations summary** | **False green** if summary **aggregates** HubSpot + jobs **without** surfacing **partial** failures from Phase 4/5 semantics. | Reuse **same** status enums as **`integration_sync_run`** and batch **`failed`/`completed_with_errors`** — Story 6.4 acceptance. |

---

## 8. Related documents

- `docs/architecture/database-schema.md` — §3.2 (`users.primary_auth`), §3.30–§3.35, §6 RLS Phase 6 row, §11 Phase 6 summary  
- `docs/architecture/api-contracts.md` — §11 (Phase 6), §12–§13 error codes and auth matrix  
- `docs/architecture/guidelines-for-tech-lead.md` — §11e  
- `docs/requirements/phase-6-requirements.md` — locked stories **6.1–6.4** and **approved product decisions**

---

**Status:** APPROVED (architecture alignment) · **2026-04-06** — Delta vs Phase 5 for enterprise identity and governance. Implementation requires `@technical-architect` design review on open items in §6 before freeze.
