# Guidelines for Tech Lead — Read Before Writing Code

**Status:** APPROVED  
**Approved:** 2026-04-06 (April 6, 2026) — §11b Phase 3; **§11c Phase 4** HubSpot; **§11d Phase 5** forecast, cost, FX, segments; **§11e Phase 6** SSO, audit export, admin operations; **§11f Phase 7** customer matrix, variance, workbook template I/O (see **2026-04-08**)  
**Source of truth:** This document is authoritative for implementation. The Tech Lead must not deviate from it without `@technical-architect` review and explicit approval.

**Audience:** Tech Lead (primary), all implementers  
**Purpose:** Enforce consistency, security, and product alignment from the first commit.

---

## 1. Project folder structure (canonical)

Use this layout; extend with **new files inside existing buckets** rather than inventing parallel trees.

```
revenue-intelligence-platform/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app factory, router include
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic Settings — ONLY place for env-derived config
│   │   │   ├── database.py       # Async engine, session factory, RLS session vars
│   │   │   ├── security.py       # Password hashing, JWT create/verify, auth deps; Phase 6: OIDC/SAML validation — IdP secrets only via settings/vault
│   │   │   └── semantic_layer.py # Load / validate semantic_layer.yaml (Phase 3)
│   │   ├── models/               # SQLAlchemy ORM — mirror database-schema.md
│   │   ├── schemas/              # Pydantic request/response DTOs
│   │   ├── api/
│   │   │   └── v1/               # routers: auth, ingest, revenue, analytics, dimensions, integrations, tenant, fx, forecast, costs, segments, audit, admin ops, health
│   │   ├── services/             # Business logic ONLY — no FastAPI objects
│   │   │   ├── ingestion/        # excel_parser, validator, loader, overlap
│   │   │   ├── analytics/        # Phase 2 aggregations (+ Phase 4 reconciliation helpers)
│   │   │   ├── integrations/     # Phase 4: hubspot/ OAuth, API client, mapper, sync
│   │   │   ├── identity/         # Phase 6: OIDC/SAML orchestration, JIT user creation, federated identity link
│   │   │   ├── forecast/         # Phase 5: series, statistical baseline, ingest helpers
│   │   │   ├── profitability/      # Phase 5: cost facts, allocation, margin service
│   │   │   ├── fx/               # Phase 5: rate table, conversion helpers (report vs ingest)
│   │   │   ├── segments/         # Phase 5: rule evaluation, materialization jobs
│   │   │   └── query_engine/     # Phase 3: NL → plan → validate → execute (+ Phase 5 measures)
│   │   ├── repositories/         # Data access — SQLAlchemy queries, unit-of-work helpers
│   │   ├── tasks/                # Celery: ingest_tasks, sync_tasks (Phase 4)
│   │   └── utils/                # Pure helpers (dates, money formatting)
│   ├── migrations/               # Alembic only
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/           # feature folders: upload/, revenue/, query/, shared/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/             # API client — axios/fetch wrappers
│   │   ├── store/                # Zustand — UI-only state
│   │   ├── types/                # TypeScript types mirroring API contracts
│   │   └── main.tsx
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── architecture/             # This doc, schema, API contracts
│   └── requirements/
├── docker-compose.yml
├── .env.example
└── README.md
```

| Location | What belongs |
|----------|----------------|
| `api/v1/` | Routers: parse input, call services, map exceptions to HTTP. **No** raw SQL. |
| `services/` | Orchestration, domain rules, transactions boundaries. |
| `repositories/` | DB queries, filters, pagination; returns models or DTOs. |
| `models/` | SQLAlchemy table definitions only. |
| `schemas/` | Pydantic — API contracts and validation. |
| `tasks/` | Celery tasks: deserialize args, call services, update batch status. |

---

## 2. Backend coding standards

### 2.1 FastAPI

- **Async** endpoints that do I/O (`async def`); use `AsyncSession`.
- **Dependencies:** `get_db`, `get_current_user`, `get_tenant_context`.
- **Status codes:** 201/202 where appropriate; **409** for overlap/conflict; **422** validation; **401/403** auth.
- **OpenAPI:** `summary=` and `description=` on every route.
- **Never** return raw stack traces to clients for expected validation failures — use structured error bodies per `api-contracts.md`.

### 2.2 SQLAlchemy

- **2.0 style:** `Mapped[]`, `mapped_column`, async session.
- **Money:** `Mapped[Decimal] = mapped_column(Numeric(18, 4), ...)`.
- **Queries:** SQLAlchemy Core / ORM with bound parameters; **no** f-string SQL.
- **Transactions:** One transaction per ingestion load; commit once on success.
- **Session `SET LOCAL`:** After acquiring connection, set `app.tenant_id` / `app.user_id` for RLS before queries.

### 2.3 Async rules

- Do not block the event loop: file parsing in thread pool or Celery for large files.
- External HTTP (OpenAI): use `httpx` async client with timeouts from settings.

---

## 3. Frontend coding standards

- **TypeScript `strict`:** no `any` without explicit escape hatch comment.
- **Server state:** TanStack Query (cache, refetch, mutations).
- **UI state:** Zustand sparingly (auth shell, UI toggles); **not** for server cache duplication.
- **Forms:** React Hook Form + Zod schemas aligned with API payloads.
- **Styling:** Tailwind; reuse `components/shared/` for buttons, tables, layout.
- **Env:** `VITE_API_URL` only via `import.meta.env`; no hardcoded production URLs.

---

## 4. What the Tech Lead is **NEVER** allowed to do

| Violation | Why |
|-----------|-----|
| Execute **raw LLM-generated SQL** against PostgreSQL | Security and correctness — use structured plan + validator + parameterized generator. |
| **Hardcode** API keys, OAuth secrets, or **`OPENAI_MODEL`** | Configuration and audit; use `settings`. |
| Use **float** for money in DB, APIs, or JS business logic | Use `Decimal` / `NUMERIC(18,4)` / string amounts in JSON as decimal strings if needed. |
| **`os.getenv()`** scattered in code | Centralize in `core/config.py`. |
| **Manual `ALTER TABLE`** outside Alembic | Governance and reproducibility. |
| **Partial commit** of Excel rows in Phase 1 | Product rule: fail entire file. |
| **Silent** import success when validation failed | Explicit batch `failed` and user-visible errors. |
| **Bypass** RLS in app code for “convenience” in production | Use migration `BYPASSRLS` only for controlled jobs if ever required, documented. |

---

## 5. Layering: API → Service → Repository → Database

```
Request
  → Router (validate HTTP, auth)
      → Schema validation (Pydantic)
          → Service (business rules, transaction start)
              → Repository (queries, ORM)
                  → PostgreSQL
          → Service (commit/rollback, domain events)
  → Response schema
```

- **Repositories** return domain-friendly structures or ORM instances; **services** decide cross-table rules (overlap detection, replace).
- **Routers** do not call repositories directly for non-trivial flows.

---

## 6. Celery tasks

- **Location:** `app/tasks/ingest_tasks.py` and **`app/tasks/sync_tasks.py`** (Phase 4 HubSpot sync).
- **Pattern:** Ingest task receives `batch_id`, loads `IngestionBatch` row, delegates to `ExcelIngestionPipeline` / `IngestionService`. Sync tasks receive `sync_run_id` / `tenant_id`, call `services/integrations/hubspot/`, update `integration_sync_run`.
- **Idempotency:** Task body safe to retry; facts use `ON CONFLICT` per idempotency strategy in `database-schema.md`.
- **Retries:** `autoretry_for`, `retry_backoff`, max retries **3**, hard time limit **30 minutes** per product assumption.
- **Redis:** Broker URL from `settings.REDIS_URL`; result backend optional (prefer DB status over Redis for source of truth).
- **Logging:** Structured log with `batch_id`, `tenant_id`, task id.

---

## 7. OpenAI usage (Phase 3)

- **Only** through a single client module (e.g. `services/query_engine/llm_client.py`).
- **Model:** `settings.OPENAI_MODEL` — **never** a string literal in call sites.
- **Keys:** `settings.OPENAI_API_KEY`; tests use mocks or env overrides.
- **Output:** Treat model output as **untrusted**; only validated structures proceed to SQL generation.

---

## 8. Error handling

- **Domain errors:** Custom exceptions (`OverlapRejected`, `ValidationFailed`) caught in routers or exception handlers → stable error codes in JSON body.
- **HTTP mapping:** 400 user fixable, 401/403 auth, 404 not found, 409 conflict, 413 payload too large, 500 unexpected (logged, generic message to client).
- **No bare `except:`** — catch specific types; log `exc_info=True` for 500 paths.

---

## 9. Logging

- **Library:** Python `logging`; structured key-value in message or `extra={}`.
- **Include:** `tenant_id`, `user_id`, `batch_id`, `request_id` (middleware).
- **Never log:** passwords, tokens, full file contents, full row PII at INFO in production.
- **Levels:** INFO for successful business events, WARNING for retries, ERROR for failures.

---

## 10. Environment configuration

- **`.env`** / deployment env vars drive **`Settings`** in `core/config.py`.
- **Required:** `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `OPENAI_API_KEY` (if NL enabled), `OPENAI_MODEL`, limits (`MAX_QUERY_ROWS`, `QUERY_TIMEOUT_SECONDS`).
- **Document** every new variable in `.env.example` with comment.
- **Phases:** Feature flags via settings (e.g. `ENABLE_NL_QUERY=false` in Phase 1).

---

## 11. Performance rules

| Situation | Guidance |
|-----------|----------|
| Filtering facts by date/org | Use indexes listed in `database-schema.md`; verify `EXPLAIN` in integration tests for representative data. |
| Large imports | Celery + batch inserts; configurable chunk size. |
| Repeated aggregate dashboards (Phase 2) | Materialized views; refresh on ingest completion or schedule; return `as_of` timestamp in API. |
| NL queries (Phase 3) | Strict row limit and statement timeout; prefer readonly connection. |
| Caching | Redis optional for read-heavy identical queries — **never** cache without tenant + query key; short TTL for financial data. |

---

## 11a. Phase 2 — analytics, BU scoping, and precomputation

| Topic | Rule |
|-------|------|
| **Analytics routes** | Implement under `app/api/v1/analytics.py` (or subpackage) with prefix `/analytics`; delegate to `services/analytics/` — same **API → service → repository** layering as ingestion. |
| **Single definition of revenue** | Rollup and compare endpoints **must** use the same filters and fact selection rules as `GET /revenue` (non-deleted facts, same org/BU semantics). No second ad-hoc revenue definition in the router. |
| **BU row-level access** | Join `user_business_unit_access` in auth/deps: if the user has any rows, restrict `fact_revenue` and analytics to those `business_unit_id` values; if none, keep **org-wide** behavior for that org (Phase 1 pilot compatibility). Mirror rules in RLS policies. |
| **Materialized views** | Create/refreshed via Alembic-defined objects; names and refresh behavior documented in `database-schema.md` §7. After successful refresh (or scheduled job), upsert `analytics_refresh_metadata`. |
| **Ingest → refresh** | On batch `completed`, trigger or enqueue MV refresh; handle failures without marking batch failed — record `last_error` on metadata for ops (Story 2.4). |
| **Fiscal vs calendar** | If product adds fiscal periods, add columns or MVs in a dedicated migration; do not silently reinterpret calendar `revenue_date` as fiscal without schema support. |
| **Drill-down** | Prefer extending query params on `GET /revenue` over duplicating list logic; ensure TanStack Query keys include all filter dimensions. |

---

## 11b. Phase 3 — semantic layer, NL query engine, audit

| Topic | Rule |
|-------|------|
| **Semantic layer** | Load from `core/semantic_layer.py` (and/or DB rows in `semantic_term_mapping`) bound to `semantic_layer_version` — **activate** new versions explicitly; hash/content id in DB for traceability (Story 3.1). |
| **Single definition of truth** | NL execution path **must** resolve to the **same** fact selection and period semantics as `GET /analytics/revenue/rollup`, `GET /analytics/revenue/compare`, and `GET /revenue` for equivalent filters — prefer **structured calls** into `services/analytics/` over parallel SQL that could drift. |
| **Query engine** | `services/query_engine/`: NL → plan → **validator** → parameterized read-only execution; **never** pass through raw model SQL. Enforce allowlist, `MAX_QUERY_ROWS`, `QUERY_TIMEOUT_SECONDS`, optional readonly DB role. |
| **Disambiguation** | On ambiguity (Story 3.3), return `needs_clarification` with structured `prompt_id` / choices; **no** silent guess on material interpretations. Persist session in `nl_query_session` **or** stateless signed token — document one pattern. |
| **Audit** | Append-only `query_audit_log`; populate `correlation_id` from request middleware; **365-day** retention default in primary store. List/detail only for `finance` / `it_admin` (see `api-contracts.md` §8). |
| **PII** | Do not log full prompts at INFO; align redaction with compliance; `natural_query` in audit per policy. |
| **Rate limits & LLM** | Configure NL and OpenAI timeouts in settings; return `503` / `429` with stable codes — no provider stack traces to clients. |
| **Feature flag** | `ENABLE_NL_QUERY` (or equivalent) must allow disabling NL without removing Phase 2 analytics. |

---

## 11c. Phase 4 — HubSpot OAuth, incremental sync, mapping, reconciliation

| Topic | Rule |
|-------|------|
| **Credentials** | HubSpot **app** id/secret and redirect URLs **only** in `core/config.py` / settings — same discipline as `OPENAI_API_KEY`. **Never** log access/refresh tokens or `encrypted_token_bundle` at INFO. |
| **HTTP client** | HubSpot API calls via **`httpx`** (async) with timeouts, retries on **429** with backoff, and **idempotent** sync steps — document behavior for partial failure (Story 4.2). |
| **Workers** | Sync jobs in **`tasks/sync_tasks.py`** (or equivalent): enqueue from `POST /integrations/hubspot/sync` and optional **Celery Beat** schedule; update `integration_sync_run` and `hubspot_sync_cursor` in **one coherent design** with architect-approved semantics. |
| **Facts** | HubSpot deals load into **`fact_revenue`** with `source_system = 'hubspot'` and **distinct** `external_id` from Excel rows — **no** `ON CONFLICT` that replaces Excel-sourced booked actuals for the same business meaning; use **`revenue_source_conflict`** and reconciliation APIs when rules collide (PRD §5 decision 5). |
| **Authority** | Excel (and in-app manual adjustments) **wins** for booked actuals in scope; HubSpot rows are **pipeline/CRM** unless product explicitly labels otherwise — NL and analytics **must** avoid ambiguous “total revenue” when both sources exist (filter by `source_system` or separate measures per `phase-4-changes.md`). |
| **Mapping** | Resolve HubSpot company/deal ids via **`hubspot_id_mapping`**; unmapped rows **do not** silently land as wrong `customer_id` — queue **exceptions** (`mapping-exceptions` API). |
| **Audit** | Sync start/end and error summaries in **`integration_sync_run`**; align with **`audit_event`** only if product needs unified stream — avoid duplicate contradictory statuses. |
| **Correlation** | Propagate **`X-Request-Id`** / **`X-Correlation-Id`** from manual sync API through Celery task to sync run record (Story 4.2 / parent PRD §4). |
| **Feature flag** | `ENABLE_HUBSPOT` (or equivalent) must allow disabling CRM ingestion **without** breaking Excel ingest, Phase 2 analytics, or Phase 3 NL. |

---

## 11d. Phase 5 — forecast, profitability, segmentation, multi-currency

| Topic | Rule |
|-------|------|
| **Separate actuals vs forecast** | **`fact_revenue`** = actuals (Excel + HubSpot per Phase 4 rules). **`fact_forecast`** = forward periods only. **Never** sum or UNION in SQL for default APIs without explicit `metric_type` / `series_id` — Story 5.1 and PRD double-counting prevention. |
| **“Revenue” language** | Rollups and NL **must** label **booked actuals** vs **forecast** vs **FX-adjusted** measures; reuse Phase 4 **source_system** discipline for CRM vs Excel actuals — Phase 5 adds measure keys, not ambiguous synonyms. |
| **FX** | **`fx_rate`** is authoritative for manual v1 uploads. Conversion order (**ingest vs report vs layered**) is **one** architected strategy per deployment — document in OpenAPI and `phase-5-changes.md`. **No silent FX:** responses that show reporting currency **must** expose basis (rate date, pair) when native ≠ reporting (Story 5.4). |
| **Rounding** | Same **NUMERIC(18,4)** rules as revenue; document rounding for cross-rate math; add regression tests (parent PRD Section 4 Quality gate). |
| **Materialized views** | If **`mv_revenue_*_reporting_currency`** or segment MVs exist, refresh when **rates** or **membership** inputs change — same class of problem as Phase 2 Story 2.4 + HubSpot MV lag (`phase-4-changes.md`). |
| **Profitability** | **`GET /analytics/profitability/summary`** (and any follow-ons) **must** call shared services that use the **same** `fact_revenue` filters as `GET /analytics/revenue/rollup` for the revenue leg — plus **`fact_cost`** and allocation rules — Story 5.2 reconciliation path. |
| **Segments** | Membership and **`GET /revenue`** / analytics **must** agree on org/BU scoping (Phase 2 RLS + Story 5.3). Materialize via **`POST /segments/definitions/{id}/materialize`** (or scheduled job) for enterprise volume — **no** ad-hoc hidden filters. |
| **Semantic layer + NL** | Extend **`semantic_layer.yaml`** (and validator allowlists) with **forecast**, **margin**, **segment**, **reporting_currency** measures — **validate-before-execute** unchanged. Extend **`query_audit_log.resolved_plan`** / status codes for FX-sensitive queries if needed — **no** raw LLM SQL. |
| **Forecast versioning** | New imports or allocation assumptions create **new** `forecast_series` / rule rows or version bumps — **no** silent in-place overwrite of published series (Story 5.1 / 5.2). |
| **Feature flags** | `ENABLE_FORECAST`, `ENABLE_PROFITABILITY`, `ENABLE_SEGMENTS`, `ENABLE_MULTI_CURRENCY` (or a single `ENABLE_PHASE5` with sub-flags) — disabling must **not** break Phase 4 HubSpot, Excel ingest, Phase 2 analytics, or Phase 3 NL **for actuals-only** paths. |

---

## 11e. Phase 6 — enterprise SSO, audit export, admin operations

| Topic | Rule |
|-------|------|
| **SSO protocols** | **OIDC first**, **SAML 2.0** second in the same release; libraries and callback URLs fixed in design review — see `phase-6-changes.md`. **Both** protocols in scope for Phase 6 GA. |
| **Secrets** | IdP client secrets, SAML private keys, signing certs — **only** environment, vault, or app-managed secure config (`core/config.py` / encrypted columns) — **never** committed; same discipline as HubSpot tokens (`§11c`). |
| **Authorization** | **Application roles** (`user_org_role`) remain **source of truth**; optional **IdP group → role** only via **`idp_group_role_mapping`** explicit rows — no implicit full sync. |
| **JIT** | **`tenant_email_domain_allowlist`** + **`tenant_security_settings.invite_only`**; first login **audited**; stable link in **`user_federated_identity`**. |
| **JWT / session** | Map OIDC/SAML success to **existing** access/refresh token shape (or documented migration); set RLS session vars from **`users`** row — IdP claims **do not** replace tenant/org/BU resolution (`database-schema.md` §6 Phase 6). |
| **Break-glass** | Email/password remains for **Super Admin** and non-interactive paths (e.g. existing API keys); **standard** users on SSO-required production tenants — **SSO only** (`phase-6-requirements.md`). |
| **Audit export** | Permission **`audit_export`** (`user_permission`); export spans **`ingestion_batch`**, **`query_audit_log`**, HubSpot **`integration_sync_run`** / connection events, **SSO/security** events — **formats** `csv` \| `jsonl` per contract; **logged** as high-risk; **rate limits** and **max window** on export endpoints. |
| **Admin operations** | **`GET /admin/operations/summary`** aggregates **existing** HubSpot + job signals — **no** second contradictory status source; align with Phase 4/5 failure semantics (no false green). |
| **Phase 5 preservation** | Phase 6 **does not** change forecast/cost/FX/segment **analytics rules** — only **governance** and **access**; `ENABLE_PHASE5` off must still yield clean actuals/Phase 4 paths. |
| **Feature flag** | `ENABLE_SSO` / `ENABLE_PHASE6` (or equivalent) — disabling SSO must **not** remove **`fact_revenue`**, HubSpot, or NL **read** paths for password-based dev/staging per environment policy. |

---

## 11f. Phase 7 — customer revenue matrix, variance, standardized workbook I/O

| Topic | Rule |
|-------|------|
| **Additive scope** | Phase 7 **extends** Phases 1–6 — no edits to locked phase requirement text; new behavior behind **`ENABLE_PHASE7`** (or sub-flags) until GA. |
| **Single definition of revenue** | Customer matrix and comparison APIs **must** delegate to **`services/analytics/`** (or shared repositories) using the **same** `fact_revenue` filters and non-deleted semantics as **`GET /analytics/revenue/rollup`** / **`GET /revenue`** — no parallel ad-hoc SQL that drifts from Phase 2. |
| **`dim_customer`** | Add **`customer_name_common`** only — **do not** rename **`customer_name`**; backfill common = legal where null. |
| **Template ingest** | **Value rows only** for `fact_revenue` in the **EUROPE Weekly Commercial v1** profile; **skip** paired delta rows; MoM/YoY from **computed** comparisons. |
| **Fail-whole-file** | Default **unchanged** from Phase 1 for the same upload path — see [`phase-7-implementation-handoff.md`](phase-7-implementation-handoff.md) decision D3. |
| **Variance** | **`revenue_variance_case`** + **`revenue_variance_explanation`** + **`variance_detection_rule`** per [`database-schema.md`](database-schema.md) §3.37–§3.39; **append-only** explanations preferred; **`audit_event`** for explain/dismiss. |
| **Notifications** | **`notification_outbox`** → email worker; recipients **`users`** in tenant directory only; deep links **TTL + single-use** — no long-lived secrets in DB columns. |
| **RLS** | New Phase 7 tables **`tenant_id`-scoped**; case visibility follows **org + BU** rules consistent with Phase 2 (`user_org_role`, `user_business_unit_access`). |
| **NL / MCP** | Optional semantic terms for customer common name / variance — **whitelist-only**; **never** raw LLM SQL. |
| **Regression** | Disabling **`ENABLE_PHASE7`** must leave Phase 1–6 APIs and ingestion **unchanged**. |

---

## 12. Vertical slice order (first implementation)

1. Config + DB session + health check  
2. Auth (register/login dev, JWT) + `users` / `tenants` seed  
3. Dimensions CRUD or seed API (minimum for Excel mapping)  
4. Object storage integration + upload API + `ingestion_batch`  
5. Excel parse/validate/load in transaction + overlap/replace rules  
6. Revenue list/read API + frontend table  
7. Phase 2: materialized views + analytics APIs  
8. Phase 3: query engine + audit log  
9. Phase 4: HubSpot OAuth + sync tasks + mapping + reconciliation APIs  
10. Phase 5: FX rates + `tenant` reporting currency · forecast ingest + `fact_forecast` · cost ingest + allocation rules · segment definitions + materialization · consolidated analytics + semantic/NL extensions  
11. Phase 6: OIDC/SAML routes + `services/identity/` · tenant SSO admin APIs · **`audit_export`** · **`/admin/operations/summary`** · permissions + security settings  
12. Phase 7: `dim_customer.customer_name_common` + variance + template registry migrations · `services/variance/`, `services/notifications/` · matrix/comparison APIs · template profile in `services/ingestion/`  

---

## 13. References

- `docs/architecture/architecture-overview.md`
- `docs/architecture/database-schema.md`
- `docs/architecture/api-contracts.md`
- `docs/architecture/phase-2-changes.md`
- `docs/architecture/phase-3-changes.md`
- `docs/architecture/phase-4-changes.md`
- `docs/architecture/phase-5-changes.md`
- `docs/architecture/phase-6-changes.md`
- `docs/architecture/phase-7-changes.md`
- `docs/architecture/phase-7-implementation-handoff.md`
- `docs/requirements/product-requirements.md`

---

**Status:** APPROVED · **2026-04-06** — Source of truth. No deviation without `@technical-architect` review. Quality Analyst sign-off required before features are marked done per project rules.
