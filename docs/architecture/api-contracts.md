# API Contracts — Enterprise Revenue Intelligence Platform

**Status:** APPROVED  
**Approved:** 2026-04-06 (April 6, 2026) — Phase 3 contracts merged; **Phase 4** HubSpot integration routes (§9); **Phase 5** forecast, cost, FX, segments (§10); **Phase 6** enterprise SSO, audit export, admin operations (§11)  
**Source of truth:** This document is authoritative for implementation. The Tech Lead must not deviate from it without `@technical-architect` review and explicit approval.

**Base path:** `/api/v1`  
**Content type:** `application/json` unless noted  
**Auth:** `Authorization: Bearer <access_token>` on all endpoints except `POST /auth/login`, `POST /auth/register` (if enabled), and `GET /health`  

**Versioning:** Prefix all routes with `/api/v1`; breaking changes require `/api/v2` or negotiated deprecation.

---

## 1. Conventions

### 1.1 Identifiers

- UUIDs in canonical string form (lowercase hex with hyphens).
- Money in JSON as **decimal strings** (e.g. `"12345.6789"`) to avoid float drift in clients — **alternatively** document numbers if both sides guarantee decimal parsing; **recommended: string** for Finance alignment.

### 1.2 Timestamps

- ISO 8601 with timezone: `2026-04-03T12:00:00Z`.

### 1.3 Error response (standard envelope)

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human-readable summary safe for end users where applicable",
    "details": null
  }
}
```

`details` may be an array of objects for field/row errors (e.g. import validation).

### 1.4 Common HTTP status codes

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 202 | Accepted (async processing) |
| 400 | Bad request / malformed |
| 401 | Unauthorized — missing or invalid token |
| 403 | Forbidden — insufficient role |
| 404 | Not found |
| 409 | Conflict — overlap import, duplicate resource |
| 413 | Payload too large |
| 422 | Validation error (Pydantic) |
| 500 | Internal error |

### 1.5 Pagination (list endpoints)

Query: `limit` (default 50, max 200), `cursor` (opaque string, optional).

Response wrapper:

```json
{
  "items": [],
  "next_cursor": null
}
```

---

## 2. Health

### `GET /health`

**Auth:** None  

**Response 200:**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## 3. Authentication

### `POST /auth/register`

**Auth:** None — **disable or protect in production** (e.g. admin-only or env flag `ALLOW_REGISTRATION`).

**Request body:**

```json
{
  "email": "user@example.com",
  "password": "minimum-entropy-rules-per-security-policy",
  "tenant_name": "Acme Corp"
}
```

**Response 201:**

```json
{
  "user_id": "uuid",
  "tenant_id": "uuid",
  "email": "user@example.com",
  "access_token": "jwt",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Errors:** `409` email exists; `422` validation.

---

### `POST /auth/login`

**Request body:**

```json
{
  "email": "user@example.com",
  "password": "string"
}
```

**Response 200:** Same token shape as register.

**Errors:** `401` invalid credentials.

---

### `POST /auth/refresh`

**Request body:**

```json
{
  "refresh_token": "string"
}
```

**Response 200:**

```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Errors:** `401` invalid/expired refresh.

---

### `GET /me`

**Auth:** Required  

**Response 200:**

```json
{
  "user_id": "uuid",
  "tenant_id": "uuid",
  "email": "user@example.com",
  "roles": [
    {
      "org_id": "uuid",
      "role": "finance"
    }
  ],
  "business_unit_scope": {
    "mode": "org_wide",
    "business_unit_ids": []
  }
}
```

**`business_unit_scope` (Phase 2):** When `mode` is `restricted`, `business_unit_ids` lists allowed BUs; when `org_wide`, Phase 2 analytics and `GET /revenue` use org-level access from `roles` only (pilot / Phase 1–compatible). Omitted only if server is pre–Phase 2 deployment.

---

## 4. Ingestion — Excel

### `POST /ingest/uploads`

**Auth:** Required — roles: `finance`, `admin`, or `it_admin` per deployment policy  

**Content type:** `multipart/form-data`  

**Parts:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | file | Yes | `.xlsx` / `.xls` per supported formats |
| org_id | string (UUID) | Yes | Target organization for facts |
| scope_org_id | string (UUID) | No | Override for overlap grain — defaults to `org_id` |
| period_start | string (date) | No | Inclusive `YYYY-MM-DD` for overlap detection |
| period_end | string (date) | No | Inclusive |
| replace | string (`"true"`/`"false"`) | No | If `true`, allow replace flow for overlapping scope |

**Response 202 (async — large file):**

```json
{
  "batch_id": "uuid",
  "status": "pending",
  "message": "Processing in background"
}
```

**Response 200 (sync — small file under threshold):**

```json
{
  "batch_id": "uuid",
  "status": "completed",
  "total_rows": 1000,
  "loaded_rows": 1000,
  "period_start": "2026-01-01",
  "period_end": "2026-03-31"
}
```

**Response 200 with failure (validation — entire file rejected):**

```json
{
  "batch_id": "uuid",
  "status": "failed",
  "total_rows": 1000,
  "loaded_rows": 0,
  "error_log": {
    "errors": [
      {
        "row": 42,
        "column": "amount",
        "message": "Amount must be a positive decimal"
      }
    ]
  }
}
```

**Errors:**

- `400` — unsupported file type  
- `403` — not allowed to upload for org  
- `409` — overlapping scope without `replace=true`  
- `413` — file exceeds max size  

**Example (curl):**

```bash
curl -X POST "$API/api/v1/ingest/uploads" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@revenue_q1.xlsx" \
  -F "org_id=550e8400-e29b-41d4-a716-446655440000"
```

---

### `GET /ingest/batches`

**Auth:** Required  

**Query:** `status`, `limit`, `cursor`  

**Response 200:**

```json
{
  "items": [
    {
      "batch_id": "uuid",
      "source_system": "excel",
      "filename": "revenue_q1.xlsx",
      "status": "completed",
      "total_rows": 1000,
      "loaded_rows": 1000,
      "error_rows": 0,
      "started_at": "2026-04-03T10:00:00Z",
      "completed_at": "2026-04-03T10:00:05Z"
    }
  ],
  "next_cursor": null
}
```

---

### `GET /ingest/batches/{batch_id}`

**Auth:** Required  

**Response 200:**

```json
{
  "batch_id": "uuid",
  "tenant_id": "uuid",
  "source_system": "excel",
  "filename": "revenue_q1.xlsx",
  "storage_key": "s3://bucket/key",
  "status": "failed",
  "total_rows": 100,
  "loaded_rows": 0,
  "error_rows": 100,
  "error_log": {
    "errors": []
  },
  "period_start": "2026-01-01",
  "period_end": "2026-03-31",
  "scope_org_id": "uuid",
  "initiated_by": "uuid",
  "started_at": "2026-04-03T10:00:00Z",
  "completed_at": "2026-04-03T10:00:02Z"
}
```

**Errors:** `404` batch not found or wrong tenant.

---

## 5. Revenue facts (read)

### `GET /revenue`

**Auth:** Required  

**Query:**

| Param | Type | Description |
|-------|------|-------------|
| org_id | UUID | Filter |
| business_unit_id | UUID | Optional |
| division_id | UUID | Optional |
| revenue_type_id | UUID | Optional — AND filter (Phase 2 drill-down; add when implementing Story 2.3 if not already shipped) |
| customer_id | UUID | Optional — AND filter (Phase 2 drill-down) |
| revenue_date_from | date | Inclusive |
| revenue_date_to | date | Inclusive |
| source_system | string | Optional — **Phase 4:** filter e.g. `excel` or `hubspot` to avoid mixing sources in drill-down. |
| limit | int | Default 50, max 200 |
| cursor | string | Pagination |

**Response 200:**

```json
{
  "items": [
    {
      "revenue_id": "uuid",
      "amount": "12345.6789",
      "currency_code": "USD",
      "revenue_date": "2026-03-15",
      "org_id": "uuid",
      "business_unit_id": "uuid",
      "division_id": "uuid",
      "customer_id": "uuid",
      "revenue_type_id": "uuid",
      "source_system": "excel",
      "batch_id": "uuid"
    }
  ],
  "next_cursor": null
}
```

**Errors:** `403` if user cannot access org.

---

## 6. Dimensions (read — Phase 1 minimum)

### `GET /organizations`

**Auth:** Required  

**Response 200:**

```json
{
  "items": [
    {
      "org_id": "uuid",
      "org_name": "Acme",
      "parent_org_id": null,
      "is_active": true
    }
  ]
}
```

---

### `GET /business-units`

**Query:** `org_id` (optional filter)  

**Response 200:** Array wrapper `items` of `{ business_unit_id, business_unit_name, org_id, is_active }`.

---

### `GET /divisions`

**Query:** `business_unit_id` (optional)  

**Response 200:** `items` of `{ division_id, division_name, business_unit_id, is_active }`.

---

### `GET /customers`

**Query:** `org_id`, pagination  

**Response 200:** `items` of `{ customer_id, customer_name, customer_code, org_id, is_active }`.

---

### `GET /revenue-types`

**Response 200:** `items` of `{ revenue_type_id, revenue_type_name, description, is_active }`.

---

## 7. Analytics (Phase 2)

**Prefix:** `/analytics` — versioned under `/api/v1` (e.g. `/api/v1/analytics/...`).  
**Money:** decimal **strings** in JSON (same as `GET /revenue`).  
**Authorization:** Same tenant as other APIs; **row-level BU scoping** applies (see `GET /me` §3): users with `user_business_unit_access` entries only see aggregates and drill-down paths for allowed BUs.  
**Freshness:** Responses that rely on precomputed structures **SHOULD** include `as_of` (ISO 8601) when available from `analytics_refresh_metadata`; see `GET /analytics/freshness`.

---

### `GET /analytics/revenue/rollup`

Hierarchical totals for Story 2.1 and filtering Story 2.3 — rolled-up revenue at the requested **hierarchy level** for an explicit date range (no ambiguous periods).

**Auth:** Required  

**Query:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hierarchy | string | Yes | `org` \| `bu` \| `division` — rollup grain. |
| revenue_date_from | date | Yes | Inclusive. |
| revenue_date_to | date | Yes | Inclusive. |
| org_id | UUID | No | Restrict subtree to this org (must be accessible). |
| business_unit_id | UUID | No | Filter (e.g. when drilling within an org). |
| division_id | UUID | No | Filter. |
| revenue_type_id | UUID | No | AND with other filters. |
| customer_id | UUID | No | AND with other filters. |

**Response 200:**

```json
{
  "hierarchy": "bu",
  "revenue_date_from": "2026-01-01",
  "revenue_date_to": "2026-03-31",
  "filters": {
    "org_id": null,
    "business_unit_id": null,
    "division_id": null,
    "revenue_type_id": null,
    "customer_id": null
  },
  "rows": [
    {
      "org_id": "uuid",
      "org_name": "Acme",
      "business_unit_id": "uuid",
      "business_unit_name": "North America",
      "division_id": null,
      "division_name": null,
      "revenue": "1000000.0000",
      "child_count": 3
    }
  ],
  "as_of": "2026-04-03T12:00:00Z"
}
```

**Semantics:** For each row, `revenue` is the **sum** of non-deleted `fact_revenue.amount` in scope; child totals reconcile to parents for the same filters and period (Story 2.1). Unused hierarchy keys are `null` on rows (e.g. `division_*` null when `hierarchy` is `bu`).

**Errors:** `403` — org/BU not accessible; `422` — invalid range or hierarchy.

---

### `GET /analytics/revenue/compare`

Period-over-period comparison for Story 2.2 — **explicit** current and comparison windows (labels returned in the payload).

**Auth:** Required  

**Query:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hierarchy | string | Yes | `org` \| `bu` \| `division`. |
| compare | string | Yes | `mom` \| `qoq` \| `yoy` — which pair of windows to compute (subset may ship in v1 per product follow-up). |
| current_period_from | date | Yes | Inclusive current window. |
| current_period_to | date | Yes | Inclusive. |
| comparison_period_from | date | Yes | Inclusive baseline window. |
| comparison_period_to | date | Yes | Inclusive. |
| org_id | UUID | No | Same filter semantics as rollup. |
| business_unit_id | UUID | No | |
| division_id | UUID | No | |
| revenue_type_id | UUID | No | |
| customer_id | UUID | No | |

**Response 200:**

```json
{
  "hierarchy": "bu",
  "compare": "yoy",
  "current_period": { "from": "2026-01-01", "to": "2026-03-31", "label": "Q1 2026" },
  "comparison_period": { "from": "2025-01-01", "to": "2025-03-31", "label": "Q1 2025" },
  "rows": [
    {
      "business_unit_id": "uuid",
      "business_unit_name": "North America",
      "current_revenue": "1000000.0000",
      "comparison_revenue": "950000.0000",
      "absolute_change": "50000.0000",
      "percent_change": "0.0526",
      "current_missing": false,
      "comparison_missing": false
    }
  ],
  "as_of": "2026-04-03T12:00:00Z"
}
```

**Missing data:** If one leg has no facts, set `current_missing` or `comparison_missing` to `true` and **omit implying zero** as confirmed revenue (Story 2.2); amounts may be `null` or `"0.0000"` with `*_missing` flags per implementation choice — document in OpenAPI.

**Errors:** `403`, `422`.

---

### `GET /analytics/freshness`

Operational and UX contract for Story 2.4 — when precomputed analytics were last refreshed and optional linkage to ingest batches.

**Auth:** Required  

**Query:** none  

**Response 200:**

```json
{
  "tenant_id": "uuid",
  "structures": [
    {
      "structure_name": "mv_revenue_monthly_by_bu",
      "last_refresh_completed_at": "2026-04-03T12:00:00Z",
      "last_completed_batch_id": "uuid"
    }
  ],
  "notes": "As-of times reflect materialized analytics; row facts via GET /revenue may be newer until refresh completes."
}
```

**Errors:** `403`.

---

### Drill-down (Story 2.3)

**No new endpoint is required** if `GET /revenue` accepts the same dimension and date filters as the summary the user drilled from. Clients **SHOULD** pass `org_id`, `business_unit_id`, `division_id`, `revenue_date_from`, `revenue_date_to`, and optional `revenue_type_id` / customer filters so detail **reconciles** to rollup totals from `GET /analytics/revenue/rollup` (same canonical `fact_revenue` rows).

Optional **future** endpoint (if product adds server-side reconciliation proofs): `GET /analytics/revenue/reconcile` — not required for Phase 2 baseline; spot-checks use Finance + `GET /revenue` totals.

---

## 8. Natural language query (Phase 3)

**Prefix:** `/query` under `/api/v1` (e.g. `/api/v1/query/...`).  
**Principles:** Interpretation uses the **semantic layer** and **same canonical revenue rules** as `GET /analytics/*` and `GET /revenue` where applicable (Stories 3.1–3.2). **No** execution of raw LLM-generated SQL — validated plan + read-only path only. **`OPENAI_MODEL`** and limits come from server settings only.

**Headers (recommended):** `X-Request-Id` or `X-Correlation-Id` (UUID) — echoed into `query_audit_log.correlation_id` for tracing (Story 3.4).

---

### `POST /query/natural-language`

**Auth:** Required — roles per deployment policy (e.g. CXO, BU Head, Finance, Viewer where product allows NL).

**Request body (initial question):**

```json
{
  "question": "What was Q3 revenue by business unit?",
  "org_id": "uuid"
}
```

**Request body (after clarification — same endpoint):**

```json
{
  "question": "What was Q3 revenue by business unit?",
  "org_id": "uuid",
  "disambiguation_token": "opaque-token-from-prior-response",
  "clarifications": [
    {
      "prompt_id": "fiscal_year",
      "choice": "2026"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| question | string | Yes | User’s natural-language question (initial or repeated with token). |
| org_id | UUID | No | Restrict interpretation to an org the user may access. |
| disambiguation_token | string | No | Returned when `status` was `needs_clarification` — resumes session server-side or validates stateless payload. |
| clarifications | array | No | Answers to structured clarification prompts; shape matches `prompt_id` / choices from prior response. |

**Response 200 — completed:**

```json
{
  "query_id": "uuid",
  "status": "completed",
  "interpretation": "Sum of revenue grouped by business unit for fiscal Q3 2026",
  "columns": ["business_unit_name", "total_revenue"],
  "rows": [
    {
      "business_unit_name": "NA",
      "total_revenue": "1000000.0000"
    }
  ],
  "disambiguation": null,
  "semantic_version_label": "2026.04.1"
}
```

**Response 200 — needs clarification (Story 3.3):**

```json
{
  "query_id": "uuid",
  "status": "needs_clarification",
  "questions": [
    {
      "prompt_id": "fiscal_year",
      "text": "Which fiscal year is Q3 in?",
      "choices": [
        { "id": "2025", "label": "FY 2025" },
        { "id": "2026", "label": "FY 2026" }
      ]
    }
  ],
  "disambiguation": {
    "token": "opaque-session-token-for-follow-up"
  }
}
```

**Errors:**

| HTTP | Code / situation |
|------|------------------|
| `400` | `QUERY_UNSAFE` — rejected by validator (Story 3.2); user-safe message, no raw SQL or stack traces. |
| `401` | Missing/invalid token. |
| `403` | Role not allowed for NL. |
| `404` | Invalid or expired `disambiguation_token` (if session-based). |
| `422` | Malformed body or unknown `prompt_id`. |
| `429` | Rate limit — LLM or tenant quota (parent PRD NL NFR). |
| `503` | LLM provider unavailable — structured error, no key leakage. |
| `504` | `QUERY_TIMEOUT` — execution or LLM exceeded configured bounds. |

**Side effects:** Successful or failed **executed** attempts append to `query_audit_log` (Story 3.4); clarification-only round-trips may log rows with `status` reflecting `needs_clarification` per product choice — **must** log **final** resolved execution with full `resolved_plan` in DB.

---

### `GET /query/audit`

**Auth:** Required — **`finance`** and/or **`it_admin`** (and optionally `admin`) per deployment; **not** for unauthenticated or generic `viewer` unless product extends matrix.

**Query:**

| Param | Type | Description |
|-------|------|-------------|
| created_from | datetime (ISO 8601) | Optional — filter `created_at` ≥ |
| created_to | datetime | Optional — filter `created_at` ≤ |
| user_id | UUID | Optional — filter by asker |
| status | string | Optional — `success`, `error`, `timeout`, `rejected_unsafe`, etc. |
| limit | int | Default 50, max 200 |
| cursor | string | Opaque pagination |

**Response 200:**

```json
{
  "items": [
    {
      "log_id": "uuid",
      "user_id": "uuid",
      "natural_query": "Q3 revenue by BU",
      "status": "success",
      "row_count": 12,
      "execution_ms": 340,
      "created_at": "2026-04-06T10:00:00Z",
      "correlation_id": "uuid"
    }
  ],
  "next_cursor": null
}
```

**Notes:** List response **may** omit full `resolved_plan` for size — use `GET /query/audit/{log_id}` for detail. **PII:** surface only what policy allows; optional redaction of `natural_query` in list view.

**Errors:** `403` — role not allowed.

---

### `GET /query/audit/{log_id}`

**Auth:** Same as `GET /query/audit`.

**Response 200:**

```json
{
  "log_id": "uuid",
  "tenant_id": "uuid",
  "user_id": "uuid",
  "correlation_id": "uuid",
  "nl_session_id": "uuid",
  "semantic_version_id": "uuid",
  "natural_query": "Q3 revenue by BU",
  "resolved_plan": {
    "kind": "structured_summary",
    "metric_keys": ["total_revenue"],
    "dimensions": ["business_unit"],
    "safe_sql_fingerprint": "sha256:…"
  },
  "execution_ms": 340,
  "row_count": 12,
  "status": "success",
  "error_message": null,
  "created_at": "2026-04-06T10:00:00Z"
}
```

**Errors:** `403`; `404` — wrong tenant or unknown id.

---

### `GET /semantic-layer/version` (optional read-only)

**Auth:** Required — `it_admin`, `finance`, or `admin` (read governance of definitions).

**Response 200:**

```json
{
  "version_id": "uuid",
  "version_label": "2026.04.1",
  "source_identifier": "semantic_layer.yaml",
  "content_sha256": "…",
  "effective_from": "2026-04-01T00:00:00Z",
  "is_active": true
}
```

**Purpose:** Story 3.1 traceability — **no** silent synonym drift without a version bump visible here.

**Errors:** `403`.

---

## 9. HubSpot integration (Phase 4)

**Prefix:** `/integrations/hubspot` under `/api/v1` (e.g. `/api/v1/integrations/hubspot/...`).  
**Principles:** Ingestion-only (no write-back to HubSpot unless a future change request). OAuth app credentials from **settings only**; tokens stored per `database-schema.md` §3.17. **Roles:** connect/disconnect and manual sync — **`it_admin`** (or delegate per product); read-only status/sync history may extend to **Finance** per deployment. **Correlation:** manual sync requests SHOULD send `X-Request-Id` / `X-Correlation-Id` (UUID) — stored on `integration_sync_run.correlation_id`.

---

### `GET /integrations/hubspot/oauth/authorize-url`

**Auth:** Required — `it_admin` (or roles product defines for connection).

**Query:** none (or optional `redirect_uri` if product allows explicit callback URLs — must match HubSpot app settings).

**Response 200:**

```json
{
  "authorization_url": "https://app.hubspot.com/oauth/authorize?...",
  "state": "opaque-csrf-token"
}
```

**Purpose:** SPA or backend initiates OAuth; client opens `authorization_url` in browser or new window. `state` MUST be validated on callback (Story 4.1).

**Errors:** `403`, `409` (already connected — optional; product may return 200 with status instead).

---

### `GET /integrations/hubspot/oauth/callback`

**Auth:** None on the request from HubSpot’s redirect (browser); MUST validate `state` and exchange `code` server-side.

**Query:** `code`, `state` (HubSpot standard OAuth parameters).

**Response:** `302` redirect to frontend success/error route with query flags, **or** `200` JSON for API-only flows — **Tech Lead:** pick one pattern and document in OpenAPI.

**Side effects:** Persists encrypted tokens to `hubspot_connection`, sets `status = connected` on success.

**Errors:** `400` invalid state/code; `502` HubSpot token endpoint failure — user-safe message.

---

### `GET /integrations/hubspot/status`

**Auth:** Required — at minimum `it_admin`; optional read for Finance per product.

**Response 200:**

```json
{
  "status": "connected",
  "hubspot_portal_id": "123456",
  "token_expires_at": "2026-04-06T15:00:00Z",
  "last_token_refresh_at": "2026-04-06T12:00:00Z",
  "last_error": null,
  "scopes_granted": "crm.objects.deals.read ..."
}
```

**`status` values:** `disconnected` · `connected` · `error` · `token_refresh_failed` (align with `hubspot_connection.status`).

**Errors:** `403`.

---

### `POST /integrations/hubspot/disconnect`

**Auth:** Required — `it_admin`.

**Request body:** `{}` (empty object) or optional `{ "confirm": true }`.

**Response 200:**

```json
{
  "status": "disconnected"
}
```

**Side effects:** Revokes or deletes stored tokens per security policy; does **not** delete historical `fact_revenue` rows — product decision for data retention.

**Errors:** `403`, `404` (no connection).

---

### `POST /integrations/hubspot/sync`

**Auth:** Required — `it_admin` or delegated roles.

**Request body:**

```json
{
  "mode": "incremental",
  "correlation_id": "uuid"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| mode | string | No | `incremental` (default) · `repair` / `full_reconciliation` — only if product supports explicit repair (Story 4.2). |
| correlation_id | UUID | No | Optional; defaults to request id from headers. |

**Response 202:**

```json
{
  "sync_run_id": "uuid",
  "status": "running",
  "message": "Sync accepted"
}
```

**Errors:** `403`, `409` (sync already running — optional), `503` (HubSpot unavailable).

---

### `GET /integrations/hubspot/sync-runs`

**Auth:** Required — `it_admin` / Finance per deployment.

**Query:** `limit`, `cursor`, optional `status`.

**Response 200:** Standard pagination wrapper — `items` with `sync_run_id`, `trigger`, `status`, `started_at`, `completed_at`, `rows_fetched`, `rows_loaded`, `rows_failed`, `error_summary`, `correlation_id`.

**Errors:** `403`.

---

### `GET /integrations/hubspot/sync-runs/{sync_run_id}`

**Auth:** Required — same as list.

**Response 200:** Full detail including `stats` JSON when present.

**Errors:** `403`, `404`.

---

### `GET /integrations/hubspot/mapping-exceptions`

**Auth:** Required — `finance`, `it_admin`, or both per product.

**Query:** `status` (`pending` | `mapped` | …), `limit`, `cursor`.

**Response 200:** Rows from `hubspot_id_mapping` (and related) where resolution is needed — **items** include `hubspot_object_type`, `hubspot_object_id`, `status`, `customer_id`, `notes`.

**Purpose:** Story 4.3 — unmapped or ambiguous entities **surface** for resolution.

**Errors:** `403`.

---

### `PATCH /integrations/hubspot/mapping-exceptions/{mapping_id}`

**Auth:** Required — `finance` / `it_admin`.

**Request body:**

```json
{
  "customer_id": "uuid",
  "org_id": "uuid",
  "status": "mapped",
  "notes": "Matched to Finance master"
}
```

**Response 200:** Updated mapping record.

**Errors:** `403`, `404`, `422`.

---

### `GET /analytics/revenue/source-reconciliation`

**Auth:** Required — **`finance`** (and optionally `it_admin`).

**Query:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| revenue_date_from | date | Yes | Inclusive. |
| revenue_date_to | date | Yes | Inclusive. |
| org_id | UUID | No | Filter. |
| customer_id | UUID | No | Filter. |
| grain | string | No | `month` \| `customer` \| `org` — aggregation grain for comparison. |

**Response 200:**

```json
{
  "revenue_date_from": "2026-01-01",
  "revenue_date_to": "2026-03-31",
  "rows": [
    {
      "org_id": "uuid",
      "customer_id": "uuid",
      "excel_total": "1000000.0000",
      "hubspot_total": "980000.0000",
      "variance": "20000.0000",
      "conflict_count": 1
    }
  ],
  "as_of": "2026-04-06T12:00:00Z"
}
```

**Semantics:** Compares **aggregates** from `fact_revenue` filtered by `source_system` (`excel` vs `hubspot`) for the same period/keys — **must not** double-count when both exist; conflict rows may also appear in `GET /integrations/hubspot/revenue-conflicts` (Story 4.3).

**Errors:** `403`, `422`.

---

### `GET /integrations/hubspot/revenue-conflicts`

**Auth:** Required — `finance`, `it_admin`.

**Query:** `status`, `limit`, `cursor`.

**Response 200:** List of `revenue_source_conflict` rows (ids, amounts, status, `detected_at`) — detail for Excel vs HubSpot authority (PRD §5 decision 5).

**Errors:** `403`.

---

### `PATCH /integrations/hubspot/revenue-conflicts/{conflict_id}`

**Auth:** Required — `finance` (and optionally `it_admin`).

**Request body:**

```json
{
  "status": "acknowledged",
  "resolution_notes": "HubSpot pipeline; Excel is booked actual"
}
```

**Response 200:** Updated conflict.

**Errors:** `403`, `404`, `422`.

---

## 10. Phase 5 — Forecast, profitability, segmentation, multi-currency

**Prefixes:** `/fx-rates`, `/forecast`, `/costs`, `/segments`, `/analytics` (extensions) under `/api/v1`.  
**Principles:** **NUMERIC** amounts as **decimal strings** in JSON; **no** implicit sum of **actuals** (`fact_revenue`) and **forecast** (`fact_forecast`) in a single metric without explicit `series` / `metric_type` parameters. **Reporting currency** is `tenants.default_currency_code` (see `GET /tenant/settings` or `GET /me` extension). **FX:** manual upload v1; optional rate API **out of scope** unless change request (parent PRD §5 decision 7). **Roles:** Finance-heavy uploads — **`finance`**, **`admin`**, **`it_admin`** per deployment; segment definition — align with Phase 2 BU scoping (Story 5.3).

---

### `GET /tenant/settings`

**Auth:** Required — `finance`, `admin`, or `it_admin` for write; read for authenticated users if product allows.

**Response 200 (read — Phase 5 fields):**

```json
{
  "tenant_id": "uuid",
  "reporting_currency_code": "USD",
  "notes": "Alias of default_currency_code per database-schema.md"
}
```

**Purpose:** Single place to read **reporting currency** for consolidation (PRD §5 decision 7). **Implementation:** May be merged into `GET /me` — if so, document in OpenAPI and mark this route optional.

**Errors:** `403`.

---

### `PATCH /tenant/settings`

**Auth:** Required — `admin` or `it_admin` (or `finance` if product allows).

**Request body (subset):**

```json
{
  "reporting_currency_code": "USD"
}
```

**Response 200:** Updated tenant settings shape.

**Errors:** `403`, `422` — invalid ISO currency.

---

### `GET /fx-rates`

**Auth:** Required — at minimum `finance` / `it_admin` for uploads; read may extend to analysts per product.

**Query:**

| Param | Type | Description |
|-------|------|-------------|
| effective_from | date | Optional — filter `effective_date` ≥ |
| effective_to | date | Optional — filter `effective_date` ≤ |
| base_currency_code | string | Optional — ISO 4217 |
| quote_currency_code | string | Optional |
| limit | int | Default 50, max 200 |
| cursor | string | Pagination |

**Response 200:** Paginated `items` with `fx_rate_id`, `base_currency_code`, `quote_currency_code`, `effective_date`, `rate` (decimal string), `rate_source`, `ingestion_batch_id`, `created_at`.

**Errors:** `403`.

---

### `POST /fx-rates/uploads`

**Auth:** Required — `finance` or `it_admin`.

**Content type:** `multipart/form-data` — rates file (CSV/Excel template per product).

**Parts:** `file` (required), optional `notes`.

**Response 202 / 200:** Same pattern as `POST /ingest/uploads` — `batch_id`, processing status.

**Errors:** `400`, `403`, `422`.

---

### `GET /forecast/series`

**Auth:** Required.

**Query:** `limit`, `cursor`, optional `source_mode` (`imported` | `statistical`).

**Response 200:** Paginated `forecast_series` summaries: `forecast_series_id`, `label`, `scenario`, `source_mode`, `effective_from`, `effective_to`, `created_at`.

**Errors:** `403`.

---

### `GET /forecast/series/{forecast_series_id}`

**Auth:** Required.

**Response 200:** Full series including `methodology` JSON (Story 5.1 transparency).

**Errors:** `403`, `404`.

---

### `POST /ingest/forecast-uploads`

**Auth:** Required — `finance`, `admin`, or `it_admin`.

**Content type:** `multipart/form-data` — `file`, `org_id` (scope), optional `label`, `scenario`.

**Response 202 / 200:** `batch_id`, `forecast_series_id` (when created), status — align with Excel ingest async semantics.

**Errors:** `400`, `403`, `409`, `422`.

---

### `GET /forecast/facts`

**Auth:** Required — BU scoping applies.

**Query:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| forecast_series_id | UUID | Yes | Which versioned run. |
| period_start_from | date | No | Inclusive. |
| period_start_to | date | No | Inclusive. |
| org_id | UUID | No | Filter. |
| business_unit_id | UUID | No | |
| customer_id | UUID | No | |
| limit | int | Default 50, max 200 | |
| cursor | string | No | |

**Response 200:** Paginated `fact_forecast` rows — `amount`, `currency_code`, `period_start`, `period_end`, dimensions — **never** labeled as audited actuals; UI must show forecast disclaimer (Story 5.1).

**Errors:** `403`, `422`.

---

### `POST /forecast/series/{forecast_series_id}/statistical-refresh`

**Auth:** Required — `finance` / `admin` (if statistical baselines enabled).

**Request body:** `{ "horizon_months": 12, "method": "trailing_average" }` — exact schema **product choice**.

**Response 202:** Job accepted to populate `fact_forecast` for this series — **clearly labeled** `source_mode = statistical`.

**Errors:** `403`, `404`, `422`.

---

### `POST /ingest/cost-uploads`

**Auth:** Required — `finance`, `admin`, or `it_admin`.

**Content type:** `multipart/form-data` — cost file + metadata (`org_id`, `cost_category` default, `period_start` / `period_end` if applicable).

**Response 202 / 200:** `batch_id`, status.

**Errors:** `400`, `403`, `422`.

---

### `GET /costs/facts`

**Auth:** Required — BU scoping.

**Query:** `cost_date_from`, `cost_date_to`, `org_id`, `business_unit_id`, `customer_id`, `cost_category`, `source_system`, `limit`, `cursor`.

**Response 200:** Paginated `fact_cost` rows — `amount`, `currency_code`, `cost_date`, `cost_category`, dimensions.

**Errors:** `403`.

---

### `GET /costs/allocation-rules`

**Auth:** Required — `finance` / `it_admin`.

**Query:** `effective_on` (date) optional — rules active on date.

**Response 200:** List of `cost_allocation_rule` rows (version, basis, effective range).

**Errors:** `403`.

---

### `POST /costs/allocation-rules`

**Auth:** Required — `finance` / `admin`.

**Request body:** `version_label`, `effective_from`, `effective_to`, `basis`, `rule_definition` (JSON).

**Response 201:** Created rule.

**Errors:** `403`, `422`.

---

### `GET /analytics/profitability/summary`

**Auth:** Required — BU scoping.

**Query:** `period_start`, `period_end`, `org_id`, `business_unit_id`, `customer_id`, `cost_scope` (e.g. `cogs_only` | `fully_loaded`) — **exact enum** per design (Story 5.2).

**Response 200:**

```json
{
  "period_start": "2026-01-01",
  "period_end": "2026-03-31",
  "revenue_total": "1000000.0000",
  "cost_total": "400000.0000",
  "margin": "600000.0000",
  "currency_code": "USD",
  "cost_scope": "cogs_only",
  "as_of": "2026-04-06T12:00:00Z",
  "methodology_note": "Costs include: …"
}
```

**Semantics:** Revenue from **`fact_revenue`** (non-deleted) per same filters as rollup; costs from **`fact_cost`** + allocated amounts per active **allocation rules** — **Tech Lead:** one service path to avoid drift. **Errors:** `403`, `422`.

---

### `GET /segments/definitions`

**Auth:** Required.

**Query:** `org_id` (optional owner filter), `is_active`, `limit`, `cursor`.

**Response 200:** Paginated segment definitions — `segment_id`, `name`, `version`, `owner_org_id`, `is_active`, `updated_at`.

**Errors:** `403`.

---

### `POST /segments/definitions`

**Auth:** Required — roles per product (e.g. `bu_head`, `finance`, `admin`).

**Request body:** `name`, `rule_definition` (JSON), optional `owner_org_id`.

**Response 201:** Created definition (`segment_id`, `version`).

**Errors:** `403`, `422`.

---

### `PATCH /segments/definitions/{segment_id}`

**Auth:** Required — same as create.

**Request body:** Optional `rule_definition`, `is_active` — **version bump** on material rule change (Story 5.3 audit).

**Response 200:** Updated segment.

**Errors:** `403`, `404`, `422`.

---

### `POST /segments/definitions/{segment_id}/materialize`

**Auth:** Required — `finance` / `admin` or delegated.

**Request body:** `{ "period_start": "2026-01-01", "period_end": "2026-03-31" }` **or** `{ "as_of_date": "2026-03-31" }` — mutual exclusion per segment **time behavior**.

**Response 202:** Membership job accepted — writes `segment_membership`.

**Errors:** `403`, `404`, `422`.

---

### `GET /segments/definitions/{segment_id}/membership`

**Auth:** Required — BU scoping; customers outside user org must not appear (Story 5.3).

**Query:** `period_start`, `period_end` **or** `as_of_date`, `segment_version`, `limit`, `cursor`.

**Response 200:** Paginated `customer_id` list (and display fields from `dim_customer` join).

**Errors:** `403`, `404`.

---

### `GET /analytics/revenue/consolidated`

**Auth:** Required — BU scoping.

**Query:** Same filters as `GET /analytics/revenue/rollup` plus: `reporting_currency` (optional override — must match tenant if not admin), `include_native_amounts` (boolean) — when true, response includes native currency and **FX metadata** per row (Story 5.4).

**Response 200:** Same shape as rollup extended with optional `reporting_amount`, `native_amount`, `native_currency_code`, `fx_rate_effective_date`, `fx_pair` for reconciliation.

**Semantics:** **Actuals only** from `fact_revenue` unless product adds explicit **forecast** toggle — default **`metric=actuals`** to avoid mixing with `fact_forecast`.

**Errors:** `403`, `422`.

---

### `GET /analytics/revenue/forecast-vs-actual`

**Auth:** Required — **explicit** combined view for board-style UX (Story 5.1 — no misleading single line).

**Query:** `forecast_series_id`, `period_start`, `period_end`, `org_id`, hierarchy level — **required** separation fields in response: `series_actual`, `series_forecast`, `period_boundary_note`.

**Response 200:** Side-by-side or keyed rows — **never** a single undifferentiated “revenue” column without labels.

**Errors:** `403`, `422`.

---

## 11. Phase 6 — Enterprise SSO, audit export, admin operations

**Prefixes:** `/auth/sso`, `/tenant/sso`, `/tenant/security`, `/audit`, `/admin/operations` under `/api/v1`.  
**Principles:** **OIDC first**, **SAML 2.0** second in the same release ([`phase-6-requirements.md`](../requirements/phase-6-requirements.md)); **application roles** remain authoritative; IdP **group → role** mapping only via **explicit** admin-configured rows. **Secrets** never in API request/response bodies — use secure server-side configuration. **Break-glass** password login remains for **Super Admin** / **service** paths per product policy; **standard** users on SSO-enabled production tenants use **SSO only**. **Rate limits** and **export size limits** apply to **SSO callbacks** and **audit export** endpoints (Story 6.2 / architect open question 8).

**Auth notes:** **Callback** routes validate **state** / **CSRF** and run server-side token exchange; responses use **non-leaky** error messages for expected failures (Story 6.1). **`audit_export`** permission (see `user_permission` in `database-schema.md`) defaults to **IT Admin**; tenant may assign **Finance** / auditor personas.

---

### SSO — OIDC (Story 6.1)

### `GET /auth/sso/oidc/login`

**Auth:** None (starts browser redirect flow) **or** optional `Authorization` for linking flows — **product choice**.

**Query:** `tenant_id` or `tenant_slug` (required — identifies which tenant’s IdP configuration to use).

**Response:** `302` redirect to IdP **authorization endpoint**, or `200` JSON `{ "authorization_url": "https://…" }` for SPA — **Tech Lead:** pick one primary pattern and document in OpenAPI.

**Errors:** `400` — SSO not configured or disabled; `429` — rate limited.

---

### `GET /auth/sso/oidc/callback`

**Auth:** None on browser redirect from IdP.

**Query:** `code`, `state` (standard OIDC/OAuth2).

**Response:** `302` redirect to application with **session** cookie or fragment token per SPA policy, **or** `200` JSON token response — align with existing `POST /auth/login` token shape.

**Side effects:** **JIT** user creation when domain allowlist matches and `tenant_security_settings.invite_only` is `false`; append **`user_federated_identity`**; issue **application JWT** with same claims shape as password login; log **`audit_event`** / security audit for success/failure.

**Errors:** `400` — invalid `state`/`code`; `403` — domain not allowlisted or invite-only; `502` — IdP unreachable — **user-safe** message; `429`.

---

### SSO — SAML 2.0 (Story 6.1)

### `GET /auth/sso/saml/login`

**Auth:** None.

**Query:** `tenant_id` or `tenant_slug` (required).

**Response:** `302` to IdP **SSO** URL (HTTP-Redirect binding) with `SAMLRequest`, or `200` with URL for client redirect.

**Errors:** Same class as OIDC login.

---

### `POST /auth/sso/saml/acs`

**Auth:** None — **SAML POST** from IdP to Assertion Consumer Service.

**Content type:** `application/x-www-form-urlencoded` (typical SAML) — **or** artifact resolution if supported (document binding).

**Response:** Same session establishment pattern as OIDC callback.

**Side effects:** Validate signature, map **`NameID`** / stable subject to **`user_federated_identity`**; JIT rules as OIDC.

**Errors:** `400` — invalid assertion; `403` — domain / invite policy; `502` — metadata/validation failure — **no** raw stack traces to clients.

---

### `GET /auth/sso/saml/metadata`

**Auth:** None — **SP metadata** for IT to upload to IdP.

**Query:** `tenant_id` or `tenant_slug`.

**Response 200:** `application/xml` SAML metadata document.

---

### Tenant SSO administration (Stories 6.1, 6.3)

### `GET /tenant/sso/configuration`

**Auth:** Required — **`it_admin`** (or `admin`).

**Response 200:** Non-secret **`sso_provider_config`** for tenant — **mask** any vault references; include `protocol`, `is_enabled`, issuer/metadata URLs, public client id, SAML entity paths.

**Errors:** `403`.

---

### `PUT /tenant/sso/configuration`

**Auth:** Required — **`it_admin`**.

**Request body:** Subset of OIDC/SAML fields per `database-schema.md` §3.30 — **no** client secrets or private keys in JSON; those use **settings UI** that writes to secure store or prompts for env rotation per deployment.

**Response 200:** Updated configuration (masked).

**Side effects:** **Audited** security-sensitive change (Story 6.3).

**Errors:** `403`, `422`, `409` — invalid metadata / conflicting protocol state.

---

### `GET /tenant/sso/domain-allowlist`

**Auth:** Required — **`it_admin`**.

**Response 200:** `{ "items": [ { "allowlist_id": "uuid", "email_domain": "example.com", "created_at": "…" } ] }`.

**Errors:** `403`.

---

### `POST /tenant/sso/domain-allowlist`

**Auth:** Required — **`it_admin`**.

**Request body:** `{ "email_domain": "example.com" }` — normalized server-side.

**Response 201:** Created row.

**Errors:** `403`, `409` duplicate, `422`.

---

### `DELETE /tenant/sso/domain-allowlist/{allowlist_id}`

**Auth:** Required — **`it_admin`**.

**Response 204.**

**Errors:** `403`, `404`.

---

### `GET /tenant/sso/group-role-mappings`

**Auth:** Required — **`it_admin`**.

**Response 200:** Paginated **`idp_group_role_mapping`** rows.

**Errors:** `403`.

---

### `POST /tenant/sso/group-role-mappings`

**Auth:** Required — **`it_admin`**.

**Request body:** `{ "idp_group_identifier": "string", "app_role": "finance", "org_id": "uuid" }`.

**Response 201:** Created mapping.

**Errors:** `403`, `422`.

---

### `PATCH /tenant/sso/group-role-mappings/{mapping_id}`

**Auth:** Required — **`it_admin`**.

**Request body:** Partial update of mapping fields.

**Response 200:** Updated mapping.

**Errors:** `403`, `404`, `422`.

---

### `DELETE /tenant/sso/group-role-mappings/{mapping_id}`

**Auth:** Required — **`it_admin`**.

**Response 204.**

**Errors:** `403`, `404`.

---

### Tenant security visibility (Story 6.3)

### `GET /tenant/security`

**Auth:** Required — **`it_admin`** (read); may extend read-only portions to **`finance`** per product.

**Response 200:**

```json
{
  "tenant_id": "uuid",
  "reporting_currency_code": "USD",
  "invite_only": false,
  "require_sso_for_standard_users": false,
  "sso_oidc_enabled": true,
  "sso_saml_enabled": false,
  "retention_notice_label": "Operational audit retention: 365 days (default)",
  "idle_timeout_minutes": null,
  "absolute_timeout_minutes": null
}
```

**Purpose:** **Surfaces** reporting currency (alias of `tenants.default_currency_code`), pilot **retention** copy hook, and **SSO/session** toggles **without** replacing Phase 5 currency engine.

**Errors:** `403`.

---

### `PATCH /tenant/security`

**Auth:** Required — **`it_admin`**.

**Request body:** Optional subset: `invite_only`, `require_sso_for_standard_users`, `retention_notice_label`, `idle_timeout_minutes`, `absolute_timeout_minutes` — **must** be **audited** (Story 6.3).

**Response 200:** Same shape as `GET`.

**Errors:** `403`, `422`.

---

### Audit export (Story 6.2)

### `POST /audit/exports`

**Auth:** Required — permission **`audit_export`** (via `user_permission` and/or default role mapping).

**Request body (example — exact field manifest fixed in design):**

```json
{
  "event_families": ["ingestion", "nl_query", "hubspot_sync", "sso_security"],
  "created_from": "2025-01-01T00:00:00Z",
  "created_to": "2026-04-06T23:59:59Z",
  "format": "csv"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| event_families | array of string | Yes | Subset of supported families; maps to `ingestion_batch`, `query_audit_log`, `integration_sync_run` / HubSpot, `audit_event` SSO — **exact** contract in OpenAPI. |
| created_from / created_to | datetime | Yes | **Operational retention** window (default **365 days** primary store). |
| format | string | Yes | `csv` · `jsonl` — **fixed in design**. |

**Response 200:** `Content-Type` appropriate for format — **stream** download with **`Content-Disposition`**; **include** `user_id` and **email** in rows where applicable for accountability (approved product decision 6).

**Response 202:** If async export is implemented — `{ "export_job_id": "uuid", "status": "pending" }` with **`GET /audit/exports/{export_job_id}`** for status/download URL.

**Side effects:** Log **high-risk** action (`audit_event` / security audit — Story 6.2).

**Errors:** `403` — missing **`audit_export`**; `413` / `422` — range too large or invalid; `429` — rate limit.

---

### `GET /audit/exports/{export_job_id}`

**Auth:** Required — **`audit_export`** (only if **async** export pattern is used).

**Response 200:** Job status and **download URL** or **redirect** — **or** `404` when expired.

---

### Admin — operational visibility (Story 6.4)

### `GET /admin/operations/summary`

**Auth:** Required — **`it_admin`**.

**Response 200 (illustrative — align with existing HubSpot + Celery semantics):**

```json
{
  "hubspot": {
    "connection_status": "connected",
    "last_sync_completed_at": "2026-04-06T12:00:00Z",
    "last_sync_run_id": "uuid",
    "last_error": null
  },
  "background_jobs": {
    "failed_recent_count": 2,
    "stuck_running_count": 0,
    "items": [
      {
        "job_type": "ingest_excel",
        "ref_id": "uuid",
        "status": "failed",
        "completed_at": "2026-04-06T11:00:00Z",
        "error_summary": "User-safe summary"
      }
    ]
  },
  "notes": "Aggregates existing Phase 4/5 signals — no duplicate contradictory status sources."
}
```

**Purpose:** **Consolidated** pilot runbook view — **must not** show **false green** when partial failures occurred (Story 6.4); heavy lists **paginated** or **time-bounded**.

**Errors:** `403`.

---

### `GET /admin/operations/background-jobs` (optional)

**Auth:** Required — **`it_admin`**.

**Query:** `status`, `since`, `limit`, `cursor`.

**Response 200:** Paginated failed/stuck/recent jobs with enough context for **retry** or **support** workflows.

**Errors:** `403`, `429`.

---

### `GET /me` (Phase 6 extension)

**Optional fields** on existing **`GET /me`** response (when SSO enabled):

```json
{
  "primary_auth": "oidc",
  "sso_required_for_user": true
}
```

**Tech Lead:** Document in OpenAPI whether these are always present or only when Phase 6 is active.

---

## 12. Error code reference (application-level)

| Code | HTTP | Meaning |
|------|------|---------|
| `UNAUTHORIZED` | 401 | Missing/invalid token |
| `FORBIDDEN` | 403 | Valid token, insufficient access |
| `NOT_FOUND` | 404 | Resource missing |
| `VALIDATION_ERROR` | 422 | Schema validation |
| `IMPORT_OVERLAP` | 409 | Overlapping scope |
| `IMPORT_VALIDATION_FAILED` | 400 | Excel validation failed (whole file) |
| `QUERY_UNSAFE` | 400 | NL query rejected by validator |
| `QUERY_TIMEOUT` | 504 | Execution exceeded limit |
| `QUERY_RATE_LIMIT` | 429 | Too many NL requests |
| `LLM_UNAVAILABLE` | 503 | Provider error or timeout |
| `HUBSPOT_TOKEN_INVALID` | 401 | OAuth refresh failed — reconnect required (optional code) |
| `HUBSPOT_RATE_LIMIT` | 429 | HubSpot API rate limit — retry later |
| `HUBSPOT_SYNC_FAILED` | 502 / 500 | Sync failed — see `integration_sync_run` detail |
| `FX_RATE_MISSING` | 422 / 409 | No rate for pair/date — cannot consolidate |
| `FORECAST_VERSION_CONFLICT` | 409 | Overlapping forecast scope without versioning strategy |
| `SEGMENT_RULE_INVALID` | 422 | Segment rule failed validation |
| `SSO_NOT_CONFIGURED` | 400 | Tenant has no usable IdP configuration |
| `SSO_DOMAIN_NOT_ALLOWED` | 403 | Email domain not on allowlist (JIT) |
| `SSO_INVITE_ONLY` | 403 | JIT disabled — user must be invited |
| `SSO_IDP_ERROR` | 502 | IdP unreachable or invalid metadata — user-safe message |
| `AUDIT_EXPORT_FORBIDDEN` | 403 | Missing `audit_export` permission |
| `AUDIT_EXPORT_TOO_LARGE` | 413 / 422 | Requested window exceeds export limits |

---

## 13. Auth matrix (summary)

| Endpoint | Auth | Notes |
|----------|------|-------|
| GET /health | No | |
| POST /auth/login | No | Rate limit |
| POST /auth/register | No | Restrict in prod |
| GET /me | Yes | |
| POST /ingest/uploads | Yes | Trusted roles |
| GET /ingest/batches* | Yes | Tenant-scoped |
| GET /revenue | Yes | Org-scoped |
| GET /dimensions* | Yes | |
| GET /analytics/revenue/rollup | Yes | Hierarchy + filters; BU RLS |
| GET /analytics/revenue/compare | Yes | PoP; BU RLS |
| GET /analytics/freshness | Yes | Phase 2 metadata |
| GET /analytics/* | Yes | Reserved for future analytics routes |
| POST /query/natural-language | Yes | NL; policy roles |
| GET /query/audit | Yes | finance / it_admin (governance) |
| GET /query/audit/{log_id} | Yes | Same |
| GET /semantic-layer/version | Yes | Optional; definition traceability |
| GET /integrations/hubspot/oauth/authorize-url | Yes | it_admin — connect |
| GET /integrations/hubspot/oauth/callback | No | OAuth redirect — validate state |
| GET /integrations/hubspot/status | Yes | it_admin / Finance (read) |
| POST /integrations/hubspot/disconnect | Yes | it_admin |
| POST /integrations/hubspot/sync | Yes | it_admin / delegate |
| GET /integrations/hubspot/sync-runs* | Yes | it_admin / Finance |
| GET /integrations/hubspot/mapping-exceptions | Yes | finance / it_admin |
| PATCH /integrations/hubspot/mapping-exceptions/{id} | Yes | finance / it_admin |
| GET /analytics/revenue/source-reconciliation | Yes | finance |
| GET /integrations/hubspot/revenue-conflicts | Yes | finance / it_admin |
| PATCH /integrations/hubspot/revenue-conflicts/{id} | Yes | finance |
| GET/PATCH /tenant/settings | Yes | read: authenticated; write: admin / it_admin / finance (per product) |
| GET /fx-rates · POST /fx-rates/uploads | Yes | finance / it_admin |
| GET /forecast/series* · GET /forecast/facts | Yes | BU-scoped |
| POST /ingest/forecast-uploads · POST …/statistical-refresh | Yes | finance / admin |
| POST /ingest/cost-uploads · GET /costs/facts | Yes | finance; BU-scoped reads |
| GET/POST /costs/allocation-rules | Yes | finance / admin |
| GET /analytics/profitability/summary | Yes | BU-scoped |
| GET/POST/PATCH /segments/* | Yes | roles per product; BU-scoped membership |
| GET /analytics/revenue/consolidated · GET /analytics/revenue/forecast-vs-actual | Yes | BU-scoped |
| GET /auth/sso/oidc/login · GET /auth/sso/oidc/callback | No* | *Callback from IdP — not Bearer; validate state/assertion |
| GET /auth/sso/saml/login · POST /auth/sso/saml/acs · GET /auth/sso/saml/metadata | No* | *Same as OAuth callbacks |
| GET/PUT /tenant/sso/configuration | Yes | it_admin |
| GET/POST/DELETE /tenant/sso/domain-allowlist* | Yes | it_admin |
| GET/POST/PATCH/DELETE /tenant/sso/group-role-mappings* | Yes | it_admin |
| GET/PATCH /tenant/security | Yes | it_admin (read may extend per product) |
| POST /audit/exports · GET /audit/exports/{id} | Yes | audit_export permission |
| GET /admin/operations/summary · GET /admin/operations/background-jobs | Yes | it_admin |

---

**Status:** APPROVED · **2026-04-06** — Source of truth (Phase 3 NL + Phase 4 HubSpot + Phase 5 enterprise intelligence + Phase 6 governance contracts). No implementation deviation without `@technical-architect` review. Contract changes require architect/product alignment.
