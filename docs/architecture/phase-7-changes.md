# Phase 7 architecture delta (vs Phase 6)

| Field | Details |
|:------|:--------|
| Status | Architecture-aligned with [`phase-7-requirements.md`](../requirements/phase-7-requirements.md) (approved 8 April 2026). Execution sequencing: [`phase-7-implementation-handoff.md`](phase-7-implementation-handoff.md). |
| Purpose | Describe what Phase 7 adds for customer revenue operations, standardized workbook I/O, variance explanations, and notifications—without revising locked baselines for Phases 1–6. |
| Scope rule | Phases 1–6 artifacts stay as-is; this document extends the platform only. |

**Tenancy:** Dimensions and facts in this repo already use `tenant_id` on tenant-scoped tables (e.g. `dim_customer`, `fact_revenue`). Phase 7 continues that pattern—any variance or template table must include `tenant_id`. (The canonical snippet in `technical-architect.mdc` is org-centric; migrations here supersede it for tenancy.)

---

## Already exists (Phase 6 baseline)

| Area | What exists |
|------|-------------|
| Facts and hierarchy | `dim_organization`, `dim_business_unit`, `dim_division`, `dim_customer`, `fact_revenue`, and indexes from prior phases |
| Ingestion | `ingestion_batch`, Excel pipeline—Phase 7 adds a template profile (e.g. `europe_weekly_commercial_v1`) |
| Auth and audit | SSO-ready identity (Phase 6), `audit_event` patterns—reuse for explanation and notification events |
| Analytics | Phase 2 materialized views and API patterns—Phase 7 reuses query patterns for customer × division × BU |

Phase 6 did not ship customer matrix UI, variance cases, email workflows for delivery managers, or dual-name customer columns under a versioned import contract.

---

## Data model — proposed additions (Alembic required)

Concrete names and types are proposals; finalize in migration review.

| Object | Purpose |
|--------|---------|
| `dim_customer` (extend) | Add nullable `customer_name_common` `VARCHAR(255)` for the second “Customer Name” column in the reference workbook. `customer_name` remains the legal / canonical column (additive only—do not rename `customer_name` in Phase 7). Backfill: set `customer_name_common = customer_name` where null so existing rows and loaders keep stable behavior. |
| `revenue_variance_case` | One row per detected discrepancy: `tenant_id`, `org_id`, optional `business_unit_id`, `division_id`, `customer_id`, `period_month` (DATE, first-of-month bucket), `rule_id`, `severity`, `status` (`open` / `explained` / `dismissed`), `baseline_amount`, `actual_amount`, `delta` (`NUMERIC(18,4)`), `currency_code`, `created_at`, `updated_at`. Idempotency: `UNIQUE (tenant_id, rule_id, customer_id, period_month, division_id)` (refine if product allows division-null cases only). |
| `revenue_variance_explanation` | Append-only rows per case (preferred): `case_id`, `explained_by_user_id`, `explanation_text`, optional `movement_direction` (`up` / `down` / `flat`), `created_at`. Emit corresponding `audit_event` entries for compliance narratives (Story 7.3). |
| `variance_detection_rule` | Per-tenant thresholds: comparison type (e.g. MoM, YoY, vs goal when goals exist), `min_abs_delta`, `min_pct` (`NUMERIC`), optional scope FKs (`org_id` / `business_unit_id`), `is_active`, `created_at`, `updated_at`. |
| `workbook_template_version` | Registry row: optional `tenant_id` (NULL = platform-published template for the deploy), `template_key` (e.g. `europe_weekly_commercial`), `version_label` (e.g. `v1`), `content_hash`, `primary_sheet_name` (e.g. `Sheet1`), JSON `column_map`, `is_active`, `created_at`, `updated_at`. |
| `notification_outbox` | Queue email jobs: `tenant_id`, recipient `user_id`, payload JSON, token reference (opaque id or hash—not cleartext secrets), status, `created_at`, `updated_at`, `sent_at`. Deep link to variance explanation page—TTL and single-use policy (security review). |

**Indexes (typical):** `(tenant_id, customer_id, period)`, `(tenant_id, status, created_at)` on variance cases; FKs to hierarchy tables as appropriate.

**RLS:** Extend policies so delivery managers see cases for in-scope org, BU, and division per the existing role model.

---

## Import and export — reference workbook

Reference: [`samples/EUROPE_Weekly Commercial Dashboard.xlsx`](../../samples/EUROPE_Weekly%20Commercial%20Dashboard.xlsx).

| Topic | Direction |
|-------|-----------|
| Primary sheet | `Sheet1`: row 2 headers; column B = `Sr. No.`, C/D = dual names, E+ = month columns Dec 2025–Dec 2026. |
| Header detection | Match by label and/or first-of-month serial for year/month; tolerate empty column A. |
| Row pairs | Detect value vs delta rows (e.g. empty `Sr. No.` on second row)—do not double-load revenue. Architecture decision (7.1): ingest value rows only for `fact_revenue`; skip delta rows in the v1 profile; compute period-over-period in analytics or UI. |
| Other sheets | Out of scope for mandatory Phase 7.1 ingest; optional later mapping for deals/projects (`EN,NN,New Logo-CW`, `Unfulfilled Allocation - CW`, etc.). |
| Export | Emit canonical template version; include conditional formatting hints for green/red or leave to client Excel—product decision in UI story 7.4. |

---

## Services and modules (proposed)

| Piece | Role |
|-------|------|
| `services/variance/` | Rule evaluation (scheduled and post-import), case creation, idempotency keys per (customer, month, rule). |
| `services/notifications/` | Email to delivery manager role; template with deep link; respect Phase 6 tenant settings. |
| `services/ingestion/` (extend) | Template profile for EUROPE Weekly Commercial layout; row classification. |
| `api/routers/` | CRUD and explain variance cases; list for delivery director grid; export trigger. |

---

## HTTP API (indicative — finalize in OpenAPI)

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/revenue/customer-matrix` | Query params: org, BU, division, period range; returns grid plus direction for styling |
| `GET` | `/variance/cases` | Filters; pagination |
| `POST` | `/variance/cases/{id}/explanation` | Body: text, optional category |
| `GET` | `/workbook/template` | Current template version metadata |
| `POST` | `/imports/excel` (extend) | Optional `template_version` |

---

## Semantic layer (Phase 3) — optional extensions

Terms such as “customer common name,” “variance case,” and “month-over-month by customer” may be added without changing Phase 3’s safety pipeline—map only to whitelisted views and columns.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Duplicate customer columns confuse legacy imports | Feature flag and explicit template selection on upload |
| Email phishing or token leak | Short-lived signed URLs, HTTPS only, audit access |
| Color-only KPI UI | Pair with text or icons (PO story 7.4) |

---

## Resolved decisions

See [`phase-7-implementation-handoff.md`](phase-7-implementation-handoff.md) for full context.

| Topic | Resolution |
|-------|------------|
| Fail-whole-file vs partial | Keep Phase 1 default (fail whole file per upload transaction) for the same ingest path; partial success needs a separate approved ingest mode. |
| `customer_name` rename vs additive | Additive only: add `customer_name_common`; do not rename `customer_name`. |
| Goal sheet → variance | Out of scope for 7.1 unless PO pulls forward; may link vs-goal rules when goal data is consistently loaded (Phase 7.2+). |

---

Parent PRD: [`product-requirements.md`](../requirements/product-requirements.md)—Phase 7 section summarizes stories; authoritative detail remains in `phase-7-requirements.md`. Implementation handoff: [`phase-7-implementation-handoff.md`](phase-7-implementation-handoff.md).
