# Database Schema — Enterprise Revenue Intelligence Platform

**Status:** APPROVED  
**Approved:** 2026-04-06 (April 6, 2026) — Phase 3 semantic layer + NL audit; **Phase 4** HubSpot tables + `fact_revenue.source_metadata`; **Phase 5** forecast, cost, FX, segments; **Phase 6** SSO governance, federated identity, security/audit export (architecture baseline — implement via Alembic)  
**Source of truth:** This document is authoritative for implementation. The Tech Lead must not deviate from it without `@technical-architect` review and explicit approval.

**Audience:** Technical Architect, Tech Lead, DBA, Quality  
**Source:** `docs/requirements/product-requirements.md`, `@technical-architect`  
**ORM:** SQLAlchemy 2.0 · **Migrations:** Alembic only  

---

## 1. Principles

| Principle | Decision |
|-----------|----------|
| Primary keys | **UUID** (`gen_random_uuid()` default) — global uniqueness across services, safe merge/replication, no sequential leakage in APIs. |
| Money | **`NUMERIC(18,4)`** — never FLOAT/DOUBLE; matches Finance expectations and product NFRs. |
| Timestamps | **`TIMESTAMPTZ`** for audit fields; **`DATE`** for revenue recognition date on facts. |
| Soft delete | **`is_deleted`** on high-volume facts only where product requires; dimensions use **`is_active`**. |
| Tenancy | **`tenant_id`** on tenant-scoped tables even in dedicated deployments — enables overlap rules, future SaaS, and consistent RLS patterns. |

---

## 2. Entity relationship (summary)

```
tenants
  └── users
        └── user_org_role ──► dim_organization
        └── user_business_unit_access (Phase 2 — optional BU restriction)
  └── dim_organization
        └── dim_business_unit
              └── dim_division
  └── dim_customer (optional org link)
  └── dim_revenue_type (may be shared per deploy — see §3.6)
  └── ingestion_batch
  └── fact_revenue ──► batch, dimensions, tenant
  └── analytics_refresh_metadata (Phase 2 — freshness / “as of”)
  └── semantic_layer_version (Phase 3 — active semantic bundle / traceability)
  └── semantic_term_mapping (Phase 3 — term/synonym → canonical binding)
  └── nl_query_session (Phase 3 — server-side disambiguation follow-up; optional if stateless tokens only)
  └── query_audit_log (Phase 3 — append-only NL execution audit)
  └── audit_event (optional)
  └── hubspot_connection (Phase 4 — OAuth / connection health per tenant)
  └── hubspot_sync_cursor (Phase 4 — incremental sync cursors)
  └── hubspot_id_mapping (Phase 4 — HubSpot object → canonical customer / org)
  └── integration_sync_run (Phase 4 — sync job audit: start/end, counts, errors)
  └── revenue_source_conflict (Phase 4 — Excel vs HubSpot conflicts for Finance)
  └── hubspot_deal_staging (Phase 4 — optional raw JSON staging before fact load)
  └── fx_rate (Phase 5 — manual FX table; effective date + source label)
  └── forecast_series (Phase 5 — versioned forecast run: imported vs statistical, scenario)
  └── fact_forecast (Phase 5 — forward periods; never mixed with fact_revenue in storage)
  └── fact_cost (Phase 5 — cost lines; NUMERIC; grain per design)
  └── cost_allocation_rule (Phase 5 — versioned allocation basis; audit)
  └── segment_definition (Phase 5 — replayable segment rules)
  └── segment_membership (Phase 5 — materialized or persisted membership per period / as-of)
  └── sso_provider_config (Phase 6 — OIDC/SAML binding per tenant; no plaintext secrets)
  └── tenant_email_domain_allowlist (Phase 6 — JIT email domain allowlist)
  └── user_federated_identity (Phase 6 — stable IdP subject ↔ user link)
  └── idp_group_role_mapping (Phase 6 — optional explicit IdP group → app role)
  └── user_permission (Phase 6 — fine-grained grants e.g. audit_export)
  └── tenant_security_settings (Phase 6 — invite-only, SSO expectations, session policy fields where stored in DB)
```

---

## 3. Table definitions

### 3.1 `tenants`

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| tenant_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | One row per logical tenant; dedicated deploy may use a single seeded tenant. |
| name | VARCHAR(255) | NOT NULL | NO | Display / admin. |
| default_currency_code | CHAR(3) | NOT NULL, `DEFAULT 'USD'` | NO | **Phase 5:** tenant **reporting currency** for consolidation (parent PRD §5 decision 7); single currency per tenant. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | App updates on write. |

**Indexes:** PK only (small cardinality per deploy).

**Rationale:** Product working assumptions reference **tenant + grain** for overlap detection; keeps a single place for reporting currency default.

---

### 3.2 `users`

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| user_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| email | VARCHAR(320) | NOT NULL | NO | Unique per tenant (see index). |
| password_hash | VARCHAR(255) | | YES | Null if **Phase 6** SSO is the sole interactive auth path for this user; **Super Admin** / **break-glass** may retain password per product policy. |
| primary_auth | VARCHAR(50) | NOT NULL, `DEFAULT 'local'` | NO | **Phase 6:** `local` · `oidc` · `saml` — how the user **normally** signs in; **application roles** remain authoritative (Story 6.1). |
| is_active | BOOLEAN | NOT NULL, `DEFAULT TRUE` | NO | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:**

- `UNIQUE (tenant_id, email)` — login lookup.
- `INDEX idx_users_tenant (tenant_id)`.

**Mandatory vs optional:** `password_hash` optional for future auth modes; email and `tenant_id` mandatory.

---

### 3.3 `user_org_role`

Maps users to organizations within a tenant for RBAC (CXO, BU Head, Finance, IT Admin, etc.).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| user_id | UUID | FK → `users(user_id)` ON DELETE CASCADE | NO | |
| org_id | UUID | FK → `dim_organization(org_id)` ON DELETE CASCADE | NO | |
| role | VARCHAR(50) | NOT NULL | NO | Values: `admin`, `cxo`, `bu_head`, `finance`, `viewer`, `it_admin` (enforce via CHECK or app enum). |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**PK:** `(user_id, org_id)`.

**Indexes:** `INDEX idx_user_org_role_org (org_id)`.

**Phase 2 — row-level BU scoping:** Org-level membership remains here. **Restrictive** BU lists are modeled in `user_business_unit_access` (§3.3a). Evaluation order: user must have `user_org_role` for the org; if one or more `user_business_unit_access` rows exist for that user, facts are further restricted to those `business_unit_id` values (and their divisions via `fact_revenue`); if **no** BU access rows exist, org-wide visibility within the org applies (per deployment policy).

---

### 3.3a `user_business_unit_access` (Phase 2)

Optional **fine-grained** BU restriction for hierarchy analytics and `fact_revenue` RLS. If a user has **no** rows in this table, Phase 2 authorization falls back to **org-wide** access implied by `user_org_role` only (same as Phase 1 pilot behavior). If **one or more** rows exist, the user is treated as **BU-scoped**: they may only see facts and hierarchy nodes for the listed business units (and child divisions as joined from facts).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| user_id | UUID | FK → `users(user_id)` ON DELETE CASCADE | NO | |
| business_unit_id | UUID | FK → `dim_business_unit(business_unit_id)` ON DELETE CASCADE | NO | Must belong to an `org_id` the user already has via `user_org_role`. |

**PK:** `(user_id, business_unit_id)`.

**Indexes:** `INDEX idx_user_bu_access_user (user_id)`.

**RLS / app checks:** Policies and service-layer filters must ensure `fact_revenue.business_unit_id` matches an allowed BU when BU restrictions apply; facts with `business_unit_id IS NULL` need an explicit product rule (e.g. inherit org from `org_id` only for unrestricted roles).

---

### 3.4 `dim_organization`

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| org_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| org_name | VARCHAR(255) | NOT NULL | NO | |
| parent_org_id | UUID | FK → `dim_organization(org_id)` ON DELETE RESTRICT | YES | Self-referential hierarchy. |
| is_active | BOOLEAN | NOT NULL, `DEFAULT TRUE` | NO | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:**

- `INDEX idx_dim_org_tenant (tenant_id)`.
- `INDEX idx_dim_org_parent (parent_org_id)`.

---

### 3.5 `dim_business_unit`

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| business_unit_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| business_unit_name | VARCHAR(255) | NOT NULL | NO | |
| org_id | UUID | FK → `dim_organization(org_id)` ON DELETE RESTRICT | NO | |
| is_active | BOOLEAN | NOT NULL, `DEFAULT TRUE` | NO | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_dim_bu_tenant_org (tenant_id, org_id)`.

---

### 3.6 `dim_division`

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| division_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| division_name | VARCHAR(255) | NOT NULL | NO | |
| business_unit_id | UUID | FK → `dim_business_unit(business_unit_id)` ON DELETE RESTRICT | NO | |
| is_active | BOOLEAN | NOT NULL, `DEFAULT TRUE` | NO | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_dim_division_bu (business_unit_id)`.

---

### 3.7 `dim_customer`

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| customer_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| customer_name | VARCHAR(255) | NOT NULL | NO | |
| customer_code | VARCHAR(100) | | YES | |
| org_id | UUID | FK → `dim_organization(org_id)` ON DELETE SET NULL | YES | |
| is_active | BOOLEAN | NOT NULL, `DEFAULT TRUE` | NO | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:**

- `UNIQUE (tenant_id, customer_code)` WHERE `customer_code IS NOT NULL` (partial unique index) **or** `UNIQUE (tenant_id, customer_code)` if empty string disallowed — **Tech Lead:** pick one convention and enforce NOT NULL code when uniqueness required.

---

### 3.8 `dim_revenue_type`

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| revenue_type_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | Allows tenant-specific classification. |
| revenue_type_name | VARCHAR(100) | NOT NULL | NO | |
| description | TEXT | | YES | |
| is_active | BOOLEAN | NOT NULL, `DEFAULT TRUE` | NO | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `UNIQUE (tenant_id, revenue_type_name)`.

---

### 3.9 `ingestion_batch`

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| batch_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | Immutable identifier for the load. |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| source_system | VARCHAR(100) | NOT NULL | NO | e.g. `excel`, later `hubspot`. |
| filename | VARCHAR(500) | | YES | Original client filename. |
| storage_key | VARCHAR(1024) | | YES | Object storage path for raw file. |
| file_sha256 | CHAR(64) | | YES | Detect re-upload of identical bytes (optional UX). |
| status | VARCHAR(50) | NOT NULL, `DEFAULT 'pending'` | NO | `pending` · `validating` · `loading` · `completed` · `failed` · `rejected` (overlap). |
| total_rows | INTEGER | | YES | |
| loaded_rows | INTEGER | NOT NULL, `DEFAULT 0` | NO | |
| error_rows | INTEGER | NOT NULL, `DEFAULT 0` | NO | Phase 1 fail-whole-file: typically all-or-nothing. |
| error_log | JSONB | | YES | Row/column messages for Finance-friendly display. |
| period_start | DATE | | YES | Inclusive; for overlap detection. |
| period_end | DATE | | YES | Inclusive. |
| scope_org_id | UUID | FK → `dim_organization(org_id)` | YES | **Agreed grain** for overlap — may be NULL if org-agnostic in a pilot (document per deployment). |
| replace_of_batch_id | UUID | FK → `ingestion_batch(batch_id)` | YES | Audit linkage when replace flow used. |
| initiated_by | UUID | FK → `users(user_id)` | YES | |
| started_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| completed_at | TIMESTAMPTZ | | YES | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:**

- `INDEX idx_ingestion_batch_tenant_status (tenant_id, status)`.
- `INDEX idx_ingestion_batch_started (started_at DESC)`.

---

### 3.10 `fact_revenue`

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| revenue_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| amount | NUMERIC(18,4) | NOT NULL | NO | **Never FLOAT.** |
| currency_code | CHAR(3) | NOT NULL, `DEFAULT 'USD'` | NO | |
| revenue_date | DATE | NOT NULL | NO | |
| org_id | UUID | FK → `dim_organization(org_id)` ON DELETE RESTRICT | NO | |
| business_unit_id | UUID | FK → `dim_business_unit(business_unit_id)` ON DELETE RESTRICT | YES | |
| division_id | UUID | FK → `dim_division(division_id)` ON DELETE RESTRICT | YES | |
| customer_id | UUID | FK → `dim_customer(customer_id)` ON DELETE RESTRICT | YES | |
| revenue_type_id | UUID | FK → `dim_revenue_type(revenue_type_id)` ON DELETE RESTRICT | YES | |
| source_system | VARCHAR(100) | NOT NULL | NO | e.g. `excel`, `hubspot` (Phase 4). |
| external_id | VARCHAR(255) | NOT NULL | NO | Stable key for idempotency within `(source_system, external_id)` — see §5. HubSpot: typically deal id. |
| source_metadata | JSONB | | YES | **Phase 4:** Optional CRM context (pipeline/stage labels, etc.) — **no** secrets; omit for Excel rows. |
| amount_reporting_currency | NUMERIC(18,4) | | YES | **Phase 5 (optional):** persisted converted amount to `tenants.default_currency_code` when product chooses **ingest-time or cached** reporting amounts — **NULL** if conversion is **report-time only**. |
| fx_rate_id | UUID | FK → `fx_rate(fx_rate_id)` ON DELETE SET NULL | YES | **Phase 5 (optional):** rate row used when `amount_reporting_currency` is populated — supports Finance reconciliation. |
| batch_id | UUID | FK → `ingestion_batch(batch_id)` ON DELETE RESTRICT | YES | SET NULL only if policy allows orphan facts — **default:** NOT NULL after load completes. |
| is_deleted | BOOLEAN | NOT NULL, `DEFAULT FALSE` | NO | For replace flows / corrections without losing audit. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Constraints:**

- `UNIQUE (source_system, external_id)` — global idempotency for upserts and Celery retries.

**Indexes (required + query):**

- `INDEX idx_fact_revenue_date ON fact_revenue(revenue_date)`.
- `INDEX idx_fact_revenue_org ON fact_revenue(tenant_id, org_id, revenue_date)`.
- `INDEX idx_fact_revenue_bu ON fact_revenue(business_unit_id, revenue_date) WHERE business_unit_id IS NOT NULL`.
- `INDEX idx_fact_revenue_division ON fact_revenue(division_id, revenue_date) WHERE division_id IS NOT NULL`.
- `INDEX idx_fact_revenue_source ON fact_revenue(source_system, external_id)`.
- `INDEX idx_fact_revenue_batch ON fact_revenue(batch_id)`.
- **Phase 5:** `INDEX idx_fact_revenue_fx_rate ON fact_revenue(fx_rate_id) WHERE fx_rate_id IS NOT NULL` (optional).

**Check (optional):** `amount` sign per business rule (e.g. allow negative adjustments) — **product decision.**

---

### 3.11 `analytics_refresh_metadata` (Phase 2)

Tracks **when** precomputed structures (materialized views or equivalent) were last refreshed and **which ingestion state** they reflect, so APIs can return `as_of` / freshness without misstating results (Story 2.4).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| metadata_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| structure_name | VARCHAR(100) | NOT NULL | NO | e.g. `mv_revenue_monthly_by_org`, `mv_revenue_monthly_by_bu` — must match implementation. |
| last_refresh_started_at | TIMESTAMPTZ | | YES | Optional observability. |
| last_refresh_completed_at | TIMESTAMPTZ | | YES | Drives “as of” in API responses when present. |
| last_completed_batch_id | UUID | FK → `ingestion_batch(batch_id)` | YES | Last batch whose successful load triggered or completed refresh. |
| last_error | TEXT | | YES | Last refresh failure message for ops; not shown to end users as financial data. |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `UNIQUE (tenant_id, structure_name)`; `INDEX idx_analytics_refresh_tenant (tenant_id)`.

**Implementation note:** Rows may be upserted by the ingestion completion path or a scheduled job; exact trigger (on batch commit vs schedule) is per architect decision in Phase 2 design review.

---

### 3.12 `semantic_layer_version` (Phase 3)

Records **which** governed semantic bundle is active for a tenant so Finance can trace **what “revenue” and dimensions meant** at interpretation time (Story 3.1). Canonical metric/dimension definitions may live primarily in **repo artifacts** (e.g. YAML); this table provides **version identity**, activation, and **integrity** (hash) without ad-hoc synonym drift.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| version_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| version_label | VARCHAR(100) | NOT NULL | NO | e.g. `2026.04.1` or git tag — human-readable. |
| source_identifier | VARCHAR(255) | | YES | Path or label for bundled artifact(s), e.g. `semantic_layer.yaml`. |
| content_sha256 | CHAR(64) | | YES | Hash of canonical artifact bytes at activation — **traceability** for change control. |
| effective_from | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | When this version became active for NL interpretation. |
| is_active | BOOLEAN | NOT NULL, `DEFAULT TRUE` | NO | At most one active row per tenant in v1 — enforce in app or partial unique index. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_semantic_layer_version_tenant (tenant_id)`; optional `UNIQUE (tenant_id) WHERE is_active = TRUE` if single active version per tenant.

---

### 3.13 `semantic_term_mapping` (Phase 3)

**Optional DB mirror** of synonym → canonical bindings for runtime lookup and audit; may be **hydrated from** the same artifacts referenced by `semantic_layer_version`. If the Tech Lead implements **YAML-only** resolution, this table can be **omitted** or populated by migration from artifacts — but **some** durable version pointer (§3.12) remains required for traceability.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| mapping_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| version_id | UUID | FK → `semantic_layer_version(version_id)` ON DELETE CASCADE | NO | Binding is valid for this semantic version only. |
| surface_form | VARCHAR(255) | NOT NULL | NO | User-facing synonym or phrase (normalized per app rules). |
| canonical_key | VARCHAR(255) | NOT NULL | NO | Stable key in semantic layer — e.g. `metric.total_revenue`, `dimension.business_unit`. |
| kind | VARCHAR(50) | NOT NULL | NO | e.g. `metric`, `dimension`, `period_hint` — CHECK or app enum. |
| metadata | JSONB | | YES | Extra hints (unit, display name) — **no** secrets. |

**Indexes:** `INDEX idx_semantic_term_mapping_version (version_id)`; `INDEX idx_semantic_term_mapping_surface (version_id, lower(surface_form))` if case-insensitive match.

---

### 3.14 `nl_query_session` (Phase 3 — disambiguation)

Stores **server-side state** for multi-turn clarification when the client presents an **opaque** follow-up token (Story 3.3). If implementation uses **stateless** signed tokens with embedded context, this table may be empty or unused — document chosen pattern in implementation.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| nl_session_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| user_id | UUID | FK → `users(user_id)` ON DELETE CASCADE | NO | |
| status | VARCHAR(50) | NOT NULL | NO | `pending_clarification` · `completed` · `expired` · `abandoned`. |
| pending_context | JSONB | | YES | Partial plan, candidate periods/BUs/metrics — **minimize PII**; prefer IDs over free text. |
| token_hash | CHAR(64) | | YES | SHA-256 of opaque token presented to client — **never** store raw token if treated as secret. |
| expires_at | TIMESTAMPTZ | NOT NULL | NO | Short TTL (e.g. 15–60 minutes) for abandoned clarification. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_nl_query_session_user_created (user_id, created_at DESC)`; `INDEX idx_nl_query_session_expires (expires_at)` for cleanup job.

---

### 3.15 `query_audit_log` (Phase 3)

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| log_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| user_id | UUID | FK → `users(user_id)` | YES | |
| correlation_id | UUID | | YES | Propagated from `X-Request-Id` / client — UI → API → audit (Story 3.4 / ops). |
| nl_session_id | UUID | FK → `nl_query_session(nl_session_id)` ON DELETE SET NULL | YES | Set when clarification preceded execution; links **final** run to session. |
| semantic_version_id | UUID | FK → `semantic_layer_version(version_id)` ON DELETE SET NULL | YES | Which semantic bundle governed interpretation (Story 3.1). |
| natural_query | TEXT | NOT NULL | NO | Original user question; **PII policy:** minimize retention in prompts if compliance requires redaction at rest. |
| resolved_plan | JSONB | | YES | **Final** structured plan / safe SQL summary / metric keys — **not** raw unchecked LLM output (Stories 3.2, 3.3). |
| execution_ms | INTEGER | | YES | |
| row_count | INTEGER | | YES | |
| status | VARCHAR(50) | | YES | `success` · `error` · `timeout` · `rejected_unsafe` · `needs_clarification` (if logged for abandoned attempts — product choice). |
| error_message | TEXT | | YES | User-safe message for failures; no stack traces. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | Append-only — **no** in-place updates in application code. |

**Indexes:** `INDEX idx_query_audit_tenant_created (tenant_id, created_at DESC)`; `INDEX idx_query_audit_correlation (correlation_id)` WHERE `correlation_id IS NOT NULL`.

**Retention:** Default **365 days** in primary store (parent PRD); archive policy per legal.

**RLS:** Same tenant isolation as other financial tables; **no** anonymous access — admin/audit roles enforced in API (Story 3.4).

---

### 3.16 `audit_event` (recommended)

Append-only style events for imports and high-risk actions.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| event_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| user_id | UUID | FK → `users(user_id)` | YES | |
| action | VARCHAR(100) | NOT NULL | NO | e.g. `ingest.completed`, `ingest.failed`, `ingest.rejected_overlap`, `ingest.replace`. |
| entity_type | VARCHAR(100) | NOT NULL | NO | e.g. `ingestion_batch`. |
| entity_id | UUID | NOT NULL | NO | |
| payload | JSONB | | YES | Non-PII metadata. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_audit_event_tenant_created (tenant_id, created_at DESC)`.

**Phase 4:** May also record high-level integration events (e.g. `hubspot.oauth.connected`, `hubspot.sync.completed`) — **or** rely primarily on `integration_sync_run` + `hubspot_connection` status; Tech Lead: avoid duplicate audit streams without product guidance.

---

### 3.17 `hubspot_connection` (Phase 4)

One row per tenant HubSpot link (Story 4.1). **Secrets:** access/refresh tokens MUST NOT be stored in plaintext; use **application-layer encryption**, a **vault reference**, or a **dedicated secrets store** per deployment — document the chosen pattern in implementation. HubSpot **app** client id/secret stay in **environment/settings** only (parent PRD §4).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| connection_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| hubspot_portal_id | VARCHAR(64) | | YES | HubSpot portal/account id — useful for support and dedupe. |
| status | VARCHAR(50) | NOT NULL | NO | `disconnected` · `connected` · `error` · `token_refresh_failed` (or equivalent — surface in UI). |
| encrypted_token_bundle | TEXT | | YES | Ciphertext or opaque vault pointer — **never** log at INFO. |
| token_expires_at | TIMESTAMPTZ | | YES | Access token expiry if applicable. |
| scopes_granted | TEXT | | YES | Granted OAuth scopes — audit / least-privilege review. |
| last_token_refresh_at | TIMESTAMPTZ | | YES | |
| last_error | TEXT | | YES | User-safe summary for operators. |
| connected_by_user_id | UUID | FK → `users(user_id)` | YES | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `UNIQUE (tenant_id)` if at most one HubSpot connection per tenant in v1; `INDEX idx_hubspot_connection_status (tenant_id, status)`.

---

### 3.18 `hubspot_sync_cursor` (Phase 4)

Stores **incremental sync** state per object type (Story 4.2) — e.g. last successful `hs_lastmodifieddate` watermark or HubSpot search-after cursor; exact encoding is **integration-specific** and MUST be documented in the Phase 4 design note.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| cursor_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| object_type | VARCHAR(50) | NOT NULL | NO | v1: `deals` primary per PRD §5 decision 6. |
| cursor_payload | JSONB | NOT NULL | NO | Opaque-to-API cursor (timestamps, paging tokens, etc.). |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Constraints:** `UNIQUE (tenant_id, object_type)`.

---

### 3.19 `hubspot_id_mapping` (Phase 4)

**Configurable mapping** from HubSpot identifiers to canonical dimensions (Story 4.3). Unmapped or ambiguous rows drive **exceptions**, not silent misclassification.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| mapping_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| hubspot_object_type | VARCHAR(50) | NOT NULL | NO | e.g. `company`, `deal`. |
| hubspot_object_id | VARCHAR(64) | NOT NULL | NO | HubSpot’s string id. |
| customer_id | UUID | FK → `dim_customer(customer_id)` ON DELETE SET NULL | YES | Target canonical customer when resolved. |
| org_id | UUID | FK → `dim_organization(org_id)` ON DELETE SET NULL | YES | Override or supplement hierarchy mapping. |
| status | VARCHAR(50) | NOT NULL | NO | e.g. `mapped`, `pending`, `ignored`. |
| notes | TEXT | | YES | Finance/ops resolution notes — PII policy applies. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `UNIQUE (tenant_id, hubspot_object_type, hubspot_object_id)`; `INDEX idx_hubspot_mapping_tenant_status (tenant_id, status)`.

---

### 3.20 `integration_sync_run` (Phase 4)

**Audit trail** for sync jobs (Story 4.2): start, end, outcome summary, correlation for UI → worker → HubSpot → DB (aligns with parent PRD §4 audit for integration actions).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| sync_run_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| integration_code | VARCHAR(50) | NOT NULL | NO | v1: `hubspot`. |
| trigger | VARCHAR(50) | NOT NULL | NO | `schedule` · `manual` · `initial_backfill` · `repair` (exact enum — product choice). |
| initiated_by_user_id | UUID | FK → `users(user_id)` | YES | Null for scheduled runs. |
| status | VARCHAR(50) | NOT NULL | NO | `running` · `completed` · `completed_with_errors` · `failed` · `cancelled`. |
| started_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| completed_at | TIMESTAMPTZ | | YES | |
| rows_fetched | INTEGER | NOT NULL, `DEFAULT 0` | NO | |
| rows_loaded | INTEGER | NOT NULL, `DEFAULT 0` | NO | |
| rows_failed | INTEGER | NOT NULL, `DEFAULT 0` | NO | |
| error_summary | TEXT | | YES | Aggregated message; row-level detail in staging or batch error paths. |
| correlation_id | UUID | | YES | Propagate from `X-Request-Id` for manual syncs. |
| stats | JSONB | | YES | Extra counters (rate-limit waits, pages) — **no** tokens. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_integration_sync_run_tenant_started (tenant_id, started_at DESC)`.

**Link to facts:** Loads may also create `ingestion_batch` rows with `source_system = 'hubspot'` for lineage; `sync_run_id` MAY be referenced from batch metadata via `ingestion_batch` extension or `stats` — **Tech Lead:** ensure one clear story in implementation (either FK from batch to `integration_sync_run` in a future migration or document batch_id in `stats`).

---

### 3.21 `revenue_source_conflict` (Phase 4)

Records **Excel vs HubSpot** conflicts where both sources address the same **canonical reconciliation key** (Story 4.3; PRD §5 decision 5). **HubSpot must not silently overwrite** Excel-derived booked actuals; conflicts **surface here** (and optionally in APIs) for Finance.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| conflict_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| reconciliation_key | VARCHAR(512) | NOT NULL | NO | Deterministic key from architected rule (e.g. hash of tenant + customer + period + grain). |
| customer_id | UUID | FK → `dim_customer(customer_id)` | YES | |
| period_start | DATE | | YES | Inclusive — match product reconciliation window. |
| period_end | DATE | | YES | Inclusive. |
| excel_amount | NUMERIC(18,4) | | YES | Aggregate or row-level snapshot per design. |
| hubspot_amount | NUMERIC(18,4) | | YES | |
| excel_fact_id | UUID | FK → `fact_revenue(revenue_id)` | YES | Representative fact(s) — if multi-row, store pointer in `stats` JSONB. |
| hubspot_fact_id | UUID | FK → `fact_revenue(revenue_id)` | YES | |
| status | VARCHAR(50) | NOT NULL | NO | `open` · `acknowledged` · `resolved` · `dismissed`. |
| resolution_notes | TEXT | | YES | |
| detected_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_revenue_conflict_tenant_status (tenant_id, status)`; `INDEX idx_revenue_conflict_detected (tenant_id, detected_at DESC)`.

---

### 3.22 `hubspot_deal_staging` (Phase 4 — optional)

**Raw staging** for HubSpot API payloads before promotion to `fact_revenue` — supports repair/replay and validation transparency (Story 4.2). May be **omitted** if facts are written directly with full validation in memory; if omitted, document alternative for partial-failure forensics.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| staging_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| sync_run_id | UUID | FK → `integration_sync_run(sync_run_id)` ON DELETE CASCADE | NO | |
| hubspot_deal_id | VARCHAR(64) | NOT NULL | NO | |
| payload | JSONB | NOT NULL | NO | Raw deal properties — **PII**; restrict log/export per policy. |
| validation_status | VARCHAR(50) | NOT NULL | NO | `pending` · `valid` · `invalid` · `loaded`. |
| error_detail | JSONB | | YES | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_hubspot_staging_run (sync_run_id)`; `INDEX idx_hubspot_staging_deal (tenant_id, hubspot_deal_id)`.

---

### 3.23 `fx_rate` (Phase 5 — multi-currency)

Manual **FX rate table** per parent PRD §5 decision 7: **effective date**, currency pair, **NUMERIC** rate, **source label** (e.g. `manual_upload`). **Optional live rate API** remains out of scope for v1 unless pulled by change request.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| fx_rate_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| base_currency_code | CHAR(3) | NOT NULL | NO | ISO 4217 — “from” currency for the pair (fact/native side). |
| quote_currency_code | CHAR(3) | NOT NULL | NO | Typically matches `tenants.default_currency_code` (reporting) for consolidation rows. |
| effective_date | DATE | NOT NULL | NO | **No silent FX:** UI/API must expose rate date + pair + basis. |
| rate | NUMERIC(18,10) | NOT NULL | NO | Units: one **base** = **rate** × **quote** (document direction in API/OpenAPI — **Tech Lead:** pick one convention and keep consistent with analytics SQL). |
| rate_source | VARCHAR(50) | NOT NULL | NO | v1: `manual_upload`; future: `api` if approved. |
| notes | TEXT | | YES | Optional audit note (who uploaded batch). |
| ingestion_batch_id | UUID | FK → `ingestion_batch(batch_id)` ON DELETE SET NULL | YES | When rate row was created from an uploaded rates file. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Constraints / indexes:** `UNIQUE (tenant_id, base_currency_code, quote_currency_code, effective_date)` — one authoritative rate per pair per day per tenant (adjust if multiple scenarios required — **architect decision**). `INDEX idx_fx_rate_tenant_effective (tenant_id, effective_date DESC)`.

---

### 3.24 `forecast_series` (Phase 5 — Story 5.1)

**Versioned forecast “run”** — separates **imported** Finance forecasts from **statistical** baselines and supports **scenario** labels (base / upside / downside per product). **Does not** mutate prior published versions in place; new assumptions create a new series or version row per Story 5.1 acceptance (versioning / immutability).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| forecast_series_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| label | VARCHAR(200) | NOT NULL | NO | Human-readable (e.g. “FY27 Plan v3”). |
| scenario | VARCHAR(50) | | YES | `base` · `upside` · `downside` · `custom` — product enum. |
| source_mode | VARCHAR(50) | NOT NULL | NO | `imported` · `statistical` — **clear labeling** of which mode produced the series (Story 5.1). |
| methodology | JSONB | | YES | Inputs, horizon, model family (if statistical), revision pointer for imports — **transparency for Finance** (Story 5.1). |
| effective_from | DATE | | YES | First forecast period covered (inclusive) — align with `fact_forecast` grain. |
| effective_to | DATE | | YES | Last forecast period covered (inclusive). |
| superseded_by_series_id | UUID | FK → `forecast_series(forecast_series_id)` ON DELETE SET NULL | YES | Optional chain when a new series replaces a published baseline **without** deleting history. |
| created_by_user_id | UUID | FK → `users(user_id)` | YES | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_forecast_series_tenant_created (tenant_id, created_at DESC)`.

---

### 3.25 `fact_forecast` (Phase 5 — Story 5.1)

**Forward-looking amounts only** — stored separately from `fact_revenue` so **actuals** and **forecast** are never combined by accidental SQL. Numeric rules: `NUMERIC(18,4)`; currency aligns with Story 5.4.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| forecast_fact_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| forecast_series_id | UUID | FK → `forecast_series(forecast_series_id)` ON DELETE CASCADE | NO | |
| period_start | DATE | NOT NULL | NO | Inclusive forecast bucket start. |
| period_end | DATE | NOT NULL | NO | Inclusive end — match product grain (month/quarter). |
| amount | NUMERIC(18,4) | NOT NULL | NO | |
| currency_code | CHAR(3) | NOT NULL | NO | |
| org_id | UUID | FK → `dim_organization(org_id)` ON DELETE RESTRICT | NO | |
| business_unit_id | UUID | FK → `dim_business_unit(business_unit_id)` ON DELETE RESTRICT | YES | |
| division_id | UUID | FK → `dim_division(division_id)` ON DELETE RESTRICT | YES | |
| customer_id | UUID | FK → `dim_customer(customer_id)` ON DELETE RESTRICT | YES | |
| external_id | VARCHAR(255) | NOT NULL | NO | Idempotency key within `(forecast_series_id, external_id)` — **Tech Lead:** deterministic hash or file row id. |
| batch_id | UUID | FK → `ingestion_batch(batch_id)` ON DELETE RESTRICT | YES | Forecast file ingest lineage when applicable. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Constraints:** `UNIQUE (forecast_series_id, external_id)`.

**Indexes:** `INDEX idx_fact_forecast_series_period (forecast_series_id, period_start)`; `INDEX idx_fact_forecast_tenant (tenant_id, period_start)`.

---

### 3.26 `fact_cost` (Phase 5 — Story 5.2)

**Cost lines** at an agreed **grain** (match to revenue facts vs pool — **design decision**). `NUMERIC` money; source labeled for reconciliation.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| cost_fact_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| amount | NUMERIC(18,4) | NOT NULL | NO | |
| currency_code | CHAR(3) | NOT NULL | NO | |
| cost_date | DATE | NOT NULL | NO | Recognition or period anchor per product. |
| cost_category | VARCHAR(100) | NOT NULL | NO | e.g. `cogs` · `opex` — exact taxonomy **design decision** (Story 5.2 scope clarity). |
| org_id | UUID | FK → `dim_organization(org_id)` ON DELETE RESTRICT | NO | |
| business_unit_id | UUID | FK → `dim_business_unit(business_unit_id)` ON DELETE RESTRICT | YES | |
| division_id | UUID | FK → `dim_division(division_id)` ON DELETE RESTRICT | YES | |
| customer_id | UUID | FK → `dim_customer(customer_id)` ON DELETE RESTRICT | YES | |
| source_system | VARCHAR(100) | NOT NULL | NO | e.g. `excel`, `manual`, `allocated`. |
| external_id | VARCHAR(255) | NOT NULL | NO | Idempotency: `UNIQUE (tenant_id, source_system, external_id)` — align with `fact_revenue` pattern. |
| batch_id | UUID | FK → `ingestion_batch(batch_id)` ON DELETE RESTRICT | YES | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_fact_cost_tenant_date (tenant_id, cost_date)`; `INDEX idx_fact_cost_org (org_id, cost_date)`.

---

### 3.27 `cost_allocation_rule` (Phase 5 — Story 5.2)

**Versioned allocation rules** — basis (e.g. revenue, headcount), **effective dates**, **who changed** via `created_by_user_id` + timestamps; **no** silent rewrite of historical allocated results without a new rule version (Story 5.2).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| rule_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| version_label | VARCHAR(100) | NOT NULL | NO | Monotonic or semantic version per tenant policy. |
| effective_from | DATE | NOT NULL | NO | |
| effective_to | DATE | | YES | Null = open-ended. |
| basis | VARCHAR(50) | NOT NULL | NO | e.g. `revenue_share` · `headcount` — product enum. |
| rule_definition | JSONB | NOT NULL | NO | Driver refs, pool ids, weights — **documented** in technical design (Story 5.2). |
| created_by_user_id | UUID | FK → `users(user_id)` | YES | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| superseded_by_rule_id | UUID | FK → `cost_allocation_rule(rule_id)` ON DELETE SET NULL | YES | Optional chain. |

**Indexes:** `INDEX idx_cost_alloc_rule_tenant_effective (tenant_id, effective_from)`.

---

### 3.28 `segment_definition` (Phase 5 — Story 5.3)

**Replayable** segment rules — same inputs yield same membership for a given **as-of** or period (Story 5.3). Optional **org/BU ownership** for governance.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| segment_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| name | VARCHAR(200) | NOT NULL | NO | |
| rule_definition | JSONB | NOT NULL | NO | Structured rule (attributes, thresholds, hierarchy predicates) — **no** ad-hoc hidden filters; exact encoding **architect decision** (SQL-like vs builder). |
| version | INTEGER | NOT NULL, `DEFAULT 1` | NO | Bump on material rule change — audit trail. |
| owner_org_id | UUID | FK → `dim_organization(org_id)` ON DELETE SET NULL | YES | If segments can be BU-scoped (open question 7 in Phase 5 requirements). |
| is_active | BOOLEAN | NOT NULL, `DEFAULT TRUE` | NO | |
| created_by_user_id | UUID | FK → `users(user_id)` | YES | |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `UNIQUE (tenant_id, name, version)` **or** `UNIQUE (tenant_id, name)` if version is internal only — **Tech Lead:** pick one naming/version UX.

---

### 3.29 `segment_membership` (Phase 5 — Story 5.3)

Persists **materialized** or computed membership for **period** or **as-of** snapshot — supports reproducible analytics and NL alignment. **Time behavior** (snapshot vs slowly changing) is **documented per segment** in API/metadata (Story 5.3).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| membership_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE RESTRICT | NO | |
| segment_id | UUID | FK → `segment_definition(segment_id)` ON DELETE CASCADE | NO | |
| segment_version | INTEGER | NOT NULL | NO | Denormalized from `segment_definition.version` for stable replay. |
| customer_id | UUID | FK → `dim_customer(customer_id)` ON DELETE CASCADE | NO | |
| period_start | DATE | | YES | If **per-period** membership. |
| period_end | DATE | | YES | Inclusive. |
| as_of_date | DATE | | YES | If **point-in-time** from attributes. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Constraints:** Product-defined uniqueness on `(segment_id, segment_version, customer_id, period_start)` or `(segment_id, segment_version, customer_id, as_of_date)` — **exact PK/unique** is design-dependent.

**Indexes:** `INDEX idx_segment_membership_segment (segment_id, segment_version)`; `INDEX idx_segment_membership_customer (customer_id)`.

---

### 3.30 `sso_provider_config` (Phase 6 — Story 6.1)

Per-tenant **IdP binding** for **OIDC** and/or **SAML 2.0** (implementation order: OIDC first, SAML second in the same release — [`phase-6-requirements.md`](../requirements/phase-6-requirements.md)). **Secrets** (OIDC client secret, SAML private key, shared secrets) **MUST NOT** be stored in plaintext — use **environment**, **vault references**, or **application-layer encryption**; this table holds **non-secret** metadata and **public** client identifiers only.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| sso_provider_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE CASCADE | NO | |
| protocol | VARCHAR(20) | NOT NULL | NO | `oidc` · `saml` — **UNIQUE** with `tenant_id` if one row per protocol per tenant. |
| is_enabled | BOOLEAN | NOT NULL, `DEFAULT FALSE` | NO | **IT Admin**-controlled; when `TRUE`, standard users **must** use SSO per tenant policy (see `tenant_security_settings`). |
| display_name | VARCHAR(255) | | YES | Shown on login chooser / admin UI. |
| oidc_issuer | VARCHAR(2048) | | YES | OIDC issuer URL (HTTPS). |
| oidc_client_id | VARCHAR(512) | | YES | Public client id — **not** the secret. |
| oidc_authorization_endpoint | VARCHAR(2048) | | YES | Optional if discoverable from issuer metadata. |
| oidc_token_endpoint | VARCHAR(2048) | | YES | Optional if discoverable. |
| oidc_jwks_uri | VARCHAR(2048) | | YES | Optional if discoverable. |
| saml_entity_id | VARCHAR(512) | | YES | SP **entity ID** (this application’s identifier for the IdP). |
| saml_metadata_url | VARCHAR(2048) | | YES | IdP metadata URL **or** use `saml_metadata_xml` (not both huge blobs — prefer URL + cache). |
| saml_acs_url_path | VARCHAR(512) | | YES | Relative path for Assertion Consumer Service — full URL built from deployment base URL. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Constraints:** `UNIQUE (tenant_id, protocol)`.

**Indexes:** `INDEX idx_sso_provider_tenant (tenant_id)`.

---

### 3.31 `tenant_email_domain_allowlist` (Phase 6 — Story 6.1)

**JIT provisioning:** email **domain** must appear here (normalized, e.g. lowercase host) unless **`tenant_security_settings.invite_only`** forces pre-registration.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| allowlist_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE CASCADE | NO | |
| email_domain | VARCHAR(255) | NOT NULL | NO | Normalized domain (no `@`); **UNIQUE** per `tenant_id`. |
| created_by_user_id | UUID | FK → `users(user_id)` | YES | Audit — who added the domain. |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `UNIQUE (tenant_id, email_domain)`; `INDEX idx_domain_allowlist_tenant (tenant_id)`.

---

### 3.32 `user_federated_identity` (Phase 6 — Story 6.1)

Binds a **`users`** row to a **stable** IdP principal (`issuer` + `subject`) for login and **JIT** idempotency. **Email changes** at the IdP are an architect decision (see `phase-6-changes.md`); this row is the **canonical** federated key.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| federated_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| user_id | UUID | FK → `users(user_id)` ON DELETE CASCADE | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE CASCADE | NO | Denormalized for RLS/query — must match `users.tenant_id`. |
| protocol | VARCHAR(20) | NOT NULL | NO | `oidc` · `saml`. |
| idp_issuer | VARCHAR(2048) | NOT NULL | NO | OIDC issuer or SAML IdP entity id — **stable** string for the IdP. |
| idp_subject | VARCHAR(512) | NOT NULL | NO | OIDC `sub` or SAML **NameID** / stable identifier per IdP contract. |
| email_at_link | VARCHAR(320) | | YES | Snapshot at first link — **not** sole authority for access; **app roles** govern authorization. |
| first_login_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | JIT creation audit (Story 6.1). |
| last_login_at | TIMESTAMPTZ | | YES | Updated on successful SSO login. |

**Constraints:** `UNIQUE (tenant_id, idp_issuer, idp_subject)`.

**Indexes:** `INDEX idx_federated_user (user_id)`; `INDEX idx_federated_tenant (tenant_id)`.

---

### 3.33 `idp_group_role_mapping` (Phase 6 — Story 6.1)

**Optional:** map **IdP group identifiers** (string from token/assertion) to **application** `user_org_role.role` values — **explicit** rows only; **no** implicit “sync all groups” (approved product decision 5).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| mapping_id | UUID | PK, `DEFAULT gen_random_uuid()` | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE CASCADE | NO | |
| idp_group_identifier | VARCHAR(512) | NOT NULL | NO | Group id or name as emitted by IdP — document matching rules. |
| app_role | VARCHAR(50) | NOT NULL | NO | Must align with `user_org_role.role` CHECK / app enum (e.g. `finance`, `it_admin`). |
| org_id | UUID | FK → `dim_organization(org_id)` ON DELETE CASCADE | NO | Role assignment is **scoped** to an org (same model as normal RBAC). |
| created_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

**Indexes:** `INDEX idx_idp_group_map_tenant (tenant_id)`.

**Application rule:** On SSO login, if mappings exist, **apply** explicit mappings only; **do not** remove manually granted roles unless product policy says otherwise.

---

### 3.34 `user_permission` (Phase 6 — Stories 6.2, 6.3)

Fine-grained **permission codes** beyond org-scoped `user_org_role` — e.g. **`audit_export`** (approved product decision 6: default **IT Admin**; tenant may assign **Finance** / auditor).

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| user_id | UUID | FK → `users(user_id)` ON DELETE CASCADE | NO | |
| tenant_id | UUID | FK → `tenants(tenant_id)` ON DELETE CASCADE | NO | |
| permission_code | VARCHAR(64) | NOT NULL | NO | e.g. `audit_export` — **UNIQUE** with `user_id`, `tenant_id`. |

**PK:** `(user_id, tenant_id, permission_code)`.

**Indexes:** `INDEX idx_user_permission_tenant (tenant_id)`.

---

### 3.35 `tenant_security_settings` (Phase 6 — Stories 6.1, 6.3)

Optional **1:1** extension for **session** and **SSO expectation** fields when not folded into `tenants`. Keeps **reporting currency** in `tenants.default_currency_code` (Phase 5) — Phase 6 **surfaces** visibility only.

| Column | Type | Constraints | Nullable | Notes |
|--------|------|-------------|----------|-------|
| tenant_id | UUID | PK, FK → `tenants(tenant_id)` ON DELETE CASCADE | NO | |
| invite_only | BOOLEAN | NOT NULL, `DEFAULT FALSE` | NO | When `TRUE`, **disable JIT** — users must be pre-invited/registered (Story 6.1). |
| require_sso_for_standard_users | BOOLEAN | NOT NULL, `DEFAULT FALSE` | NO | When `TRUE` and IdP enabled, **standard** interactive users **must not** use password login (Story 6.1 / break-glass exceptions). |
| idle_timeout_minutes | INTEGER | | YES | Nullable = product default from settings. |
| absolute_timeout_minutes | INTEGER | | YES | Nullable = product default. |
| retention_notice_label | VARCHAR(255) | | YES | **Surface** operational retention (e.g. **365 days**) for pilots — not legal advice. |
| updated_at | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` | NO | |

---

## 4. Foreign key reference summary

| Child | Parent |
|-------|--------|
| users | tenants |
| user_org_role | users, dim_organization |
| user_business_unit_access | users, dim_business_unit |
| dim_organization | tenants, dim_organization (parent) |
| dim_business_unit | tenants, dim_organization |
| dim_division | tenants, dim_business_unit |
| dim_customer | tenants, dim_organization |
| dim_revenue_type | tenants |
| ingestion_batch | tenants, users, dim_organization (scope), ingestion_batch (replace_of) |
| fact_revenue | tenants, dimensions…, ingestion_batch, **fx_rate (Phase 5, optional)** |
| analytics_refresh_metadata | tenants, ingestion_batch |
| fx_rate | tenants, ingestion_batch (optional) |
| forecast_series | tenants, users, forecast_series (superseded chain) |
| fact_forecast | tenants, forecast_series, dimensions, ingestion_batch (optional) |
| fact_cost | tenants, dimensions, ingestion_batch (optional) |
| cost_allocation_rule | tenants, users, cost_allocation_rule (superseded) |
| segment_definition | tenants, dim_organization (optional), users |
| segment_membership | tenants, segment_definition, dim_customer |
| semantic_layer_version | tenants |
| semantic_term_mapping | semantic_layer_version |
| nl_query_session | tenants, users |
| query_audit_log | tenants, users, nl_query_session (optional), semantic_layer_version (optional) |
| hubspot_connection | tenants, users (connected_by) |
| hubspot_sync_cursor | tenants |
| hubspot_id_mapping | tenants, dim_customer, dim_organization |
| integration_sync_run | tenants, users (initiated_by) |
| revenue_source_conflict | tenants, dim_customer, fact_revenue (optional FKs) |
| hubspot_deal_staging | tenants, integration_sync_run |
| sso_provider_config | tenants |
| tenant_email_domain_allowlist | tenants, users (created_by) |
| user_federated_identity | tenants, users |
| idp_group_role_mapping | tenants, dim_organization |
| user_permission | tenants, users |
| tenant_security_settings | tenants |

---

## 5. Idempotency and duplicate imports

### 5.1 Celery / worker retries

- **Fact insert:** `ON CONFLICT (source_system, external_id) DO NOTHING` or `DO UPDATE` only when business rules say so — **Tech Lead** must ensure **retry-safety** without double counting.
- **External ID for Excel:** `external_id = 'excel:' || batch_id::text || ':' || row_number` (or deterministic hash of row content + batch) so reruns of the **same** batch produce the same keys.
- **External ID for HubSpot (Phase 4):** Use a stable string id from HubSpot (e.g. **deal** id) scoped by `source_system = 'hubspot'` so `UNIQUE (source_system, external_id)` remains the idempotency key for incremental sync retries — **do not** reuse the same key for Excel-sourced rows.

### 5.2 Overlapping scope (business rule)

- Before insert, evaluate **tenant + period + scope_org (and agreed grain)** against existing non-deleted facts or completed batches.
- **Default:** reject new batch with `status = rejected` and clear `error_log` unless **`replace=true`** on the request.
- **Replace:** single transaction: soft-delete or hard-delete facts in scope (per product policy), insert new rows, link `replace_of_batch_id`.

### 5.3 Phase 1 “fail entire file”

- No committed facts from a failed validation pass; transaction boundary around the whole load.

---

## 6. RLS policy design

**Enable RLS** on at least: `fact_revenue`, `ingestion_batch`, `semantic_layer_version`, `semantic_term_mapping`, `nl_query_session`, `query_audit_log`, `audit_event`, **`hubspot_connection`**, **`hubspot_sync_cursor`**, **`hubspot_id_mapping`**, **`integration_sync_run`**, **`revenue_source_conflict`**, **`hubspot_deal_staging`** (Phase 4), **`fx_rate`**, **`forecast_series`**, **`fact_forecast`**, **`fact_cost`**, **`cost_allocation_rule`**, **`segment_definition`**, **`segment_membership`** (Phase 5), **`sso_provider_config`**, **`tenant_email_domain_allowlist`**, **`user_federated_identity`**, **`idp_group_role_mapping`**, **`user_permission`**, **`tenant_security_settings`** (Phase 6).

| Phase | Policy intent |
|-------|----------------|
| **1** | `tenant_id = current_setting('app.tenant_id')::uuid` for all rows; optional allow-all for bootstrap scripts using `BYPASSRLS` superuser only in migrations. |
| **2** | **Org + BU visibility:** `org_id` via `user_org_role`; **BU restriction** via `user_business_unit_access` when populated. Policies or `USING` clauses should reference helper SQL functions (e.g. accessible `business_unit_id` set for `app.user_id`) to stay consistent with application-layer checks. |
| **3** | **NL audit & sessions:** `query_audit_log` and `nl_query_session` tenant-isolated; **list/detail audit APIs** additionally require `finance` / `it_admin` (or equivalent) at application layer — RLS does not replace role checks for governance views. |
| **4** | **HubSpot / integration:** Same `tenant_id` isolation; connection tokens and sync metadata visible only to **`it_admin`** (and roles product extends) at the **API** layer — RLS enforces tenant boundary, not OAuth delegation. |
| **5** | **FX / forecast / cost / segments:** Tenant isolation on all new fact tables; **Finance**-sensitive uploads (rates, forecasts, costs) enforced at **API** role layer as for ingestion — RLS does not replace role checks for governance actions. |
| **6** | **SSO / governance:** All Phase 6 tables are **`tenant_id`-scoped**; **`user_federated_identity`** must match **`app.user_id`** on self-service reads where applicable. **JWT/session** must still carry **application** `tenant_id` and **org/BU** scope — IdP claims **do not** replace **`user_org_role`**; defense-in-depth with app-layer checks (Story 6.1 / architect open question 6). |

**Example (Phase 1):**

```sql
ALTER TABLE fact_revenue ENABLE ROW LEVEL SECURITY;
CREATE POLICY fact_revenue_tenant_isolation ON fact_revenue
  FOR ALL
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

**Session variables:** API sets `SET LOCAL app.tenant_id`, `SET LOCAL app.user_id` per request (via connection checkout hook).

**Tech Lead:** Use a dedicated DB user for the app without `BYPASSRLS` in production.

---

## 7. Phase 2+ structures (documented now, implemented in Phase 2)

### 7.1 Materialized views (or equivalent rollups)

Precomputed objects **must** be listed here and kept in sync with Alembic (create/drop in migrations). Naming convention: `mv_` prefix + grain + time bucket, tenant-scoped in definition or via join to `tenants`.

| Object (illustrative) | Grain | Typical refresh |
|----------------------|-------|-----------------|
| `mv_revenue_monthly_by_org` | `tenant_id`, `org_id`, calendar month | After batch `completed` or scheduled |
| `mv_revenue_monthly_by_bu` | `tenant_id`, `business_unit_id`, calendar month | Same |
| `mv_revenue_monthly_by_division` | `tenant_id`, `division_id`, calendar month | Same |
| `mv_revenue_quarterly_by_org` (optional) | org + calendar quarter | If QoQ comparisons need it |
| `mv_revenue_reporting_currency_*` (Phase 5 — optional) | Same grains as above, **reporting currency** | When product persists pre-converted rollups — must stay consistent with `fx_rate` and documented rounding |
| `mv_segment_*` (Phase 5 — optional) | Precomputed segment × period aggregates | If on-the-fly membership is too slow at enterprise volume |

**Refresh:** `REFRESH MATERIALIZED VIEW CONCURRENTLY` where indexes support it, or transactional refresh during ingest worker; update `analytics_refresh_metadata` (§3.11) on success or record failures. **Phase 5:** FX-affected MVs must refresh when rates change if **cached** reporting amounts depend on them (open architect decision: restatement in scope for v1 — see `phase-5-changes.md`).

**Fiscal periods:** If pilots require non-calendar quarters, add either fiscal columns to these MVs or separate objects (e.g. `mv_revenue_fiscal_quarter_by_bu`) — **architect decision** (see Phase 2 open items in `phase-2-requirements.md`).

### 7.2 Partitioning (optional, volume-driven)

- **Partitioning** `fact_revenue` by `RANGE (revenue_date)` when volume warrants (per architect performance strategy).

---

## 8. Migration strategy (Alembic)

1. **Single chain:** All changes in `backend/migrations/versions/` with linear revision IDs.
2. **Review:** Any DDL requires `@technical-architect` approval; no manual `ALTER` in production.
3. **Expand–contract:** Prefer additive migrations; destructive changes behind feature flags and data backfill steps.
4. **Freeze windows:** No prod migrations during customer-declared finance freezes without written exception.
5. **Environments:** Dev/staging apply same migrations before prod; smoke test RLS policies per release.
6. **Rollback:** Prefer forward-fix migrations; document non-reversible operations in migration docstrings.

---

## 9. Phase 4 — HubSpot (implemented via dedicated migrations)

Phase 4 DDL is defined in **§3.10** (`fact_revenue.source_metadata`), **§3.17–§3.22** (`hubspot_connection`, `hubspot_sync_cursor`, `hubspot_id_mapping`, `integration_sync_run`, `revenue_source_conflict`, optional `hubspot_deal_staging`). **Excel remains authoritative** for booked revenue actuals where the PRD applies; HubSpot contributes pipeline/CRM-sourced facts and **must not** silently overwrite Excel-derived rows for the same canonical reconciliation rule — use `revenue_source_conflict` and product workflows.

See **`docs/architecture/phase-4-changes.md`** for delta vs Phase 3 and open architect decisions.

---

## 10. Phase 5 — Forecast, profitability, segmentation, multi-currency

Phase 5 DDL is defined in **§3.1** (`tenants.default_currency_code` as reporting currency), **§3.10** (optional `fact_revenue.amount_reporting_currency`, `fact_revenue.fx_rate_id`), and **§3.23–§3.29** (`fx_rate`, `forecast_series`, `fact_forecast`, `fact_cost`, `cost_allocation_rule`, `segment_definition`, `segment_membership`). **Forecast** rows live only in `fact_forecast` — **never** merge with `fact_revenue` without explicit user intent in API/UX (parent PRD + Story 5.1). **HubSpot / Excel authority** rules from Phase 4 **carry forward** for actuals.

See **`docs/architecture/phase-5-changes.md`** for delta vs Phase 4, open architect decisions, and Phase 4 regression risks.

---

## 11. Phase 6 — Enterprise identity, audit export, admin operations

Phase 6 DDL is defined in **§3.2** (`users.primary_auth`), **§3.30–§3.35** (`sso_provider_config`, `tenant_email_domain_allowlist`, `user_federated_identity`, `idp_group_role_mapping`, `user_permission`, `tenant_security_settings`). **Existing** append-only streams — **`ingestion_batch`**, **`query_audit_log`**, **`audit_event`**, **`integration_sync_run`**, **`hubspot_connection`** — are the **primary sources** for **audit export** (Story 6.2); **SSO/security** events may be recorded in **`audit_event`** (recommended action codes `sso.*`, `audit_export.*`) or a dedicated append-only table if volume warrants — document the chosen pattern in implementation.

**SSO secrets:** Never in ORM plaintext; align with **§3.17** HubSpot token handling patterns.

See **`docs/architecture/phase-6-changes.md`** for delta vs Phase 5, open architect decisions, and Phase 5 regression risks.

---

**Status:** APPROVED · **2026-04-06** (Phase 5–6 architecture baseline) — Source of truth. No implementation deviation without `@technical-architect` review. This document must stay aligned with implemented Alembic revisions; update both together.
