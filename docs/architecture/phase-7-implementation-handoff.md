# Phase 7 — implementation handoff

Tech lead · UX/UI · QA

| Field | Details |
|:------|:--------|
| Status | Ready for implementation—architecture-aligned with [`phase-7-requirements.md`](../requirements/phase-7-requirements.md) (8 April 2026) |
| Scope | Additive only. Phases 1–6 behavior, APIs, and schemas remain valid; Phase 7 extends the platform without rewriting locked phase contracts. |
| Authoritative deltas | [`phase-7-changes.md`](phase-7-changes.md) (schema and API intent), this document (sequencing and handoff), [`database-schema.md`](database-schema.md) §3.7 / §3.36–§3.40 when merged. |

---

## Purpose

Single entry point for:

- **Technical lead:** Vertical slices, dependencies, feature flags, and non-negotiables from architecture.
- **UX/UI:** Screen and story mapping, accessibility constraints, and template labeling (see project UX rules).
- **QA:** Regression scope (Phases 1–6), new acceptance surfaces for Phase 7, and security-sensitive flows (email links, tenancy).

**Product intent:** Customer-level revenue matrix, hierarchical comparisons, variance cases with audited explanations, email plus deep link, and versioned Excel template interop for [`samples/EUROPE_Weekly Commercial Dashboard.xlsx`](../../samples/EUROPE_Weekly%20Commercial%20Dashboard.xlsx) `Sheet1` as v1 primary.

---

## Baseline — what must not regress

| Area | Rule |
|------|------|
| Phases 1–6 | No change to locked requirements documents; existing ingestion, analytics, NL pipeline (Phase 3 safety rules), HubSpot, FX/forecast/segments, SSO—unchanged unless a Phase 7 story explicitly extends an endpoint with optional fields. |
| Money and keys | `NUMERIC(18,4)` for amounts; UUID primary keys; `UNIQUE(source_system, external_id)` on `fact_revenue` remains the idempotency contract for fact loads. |
| Tenancy | All tenant-scoped rows include `tenant_id` (matches implemented ORM—see `DimOrganization`, `FactRevenue`, etc.). Phase 7 tables must include `tenant_id`. |
| RLS | New tables use the same `app.tenant_id` session pattern as existing facts and governance tables. |
| MCP / NL | No raw LLM SQL; optional semantic-layer terms for Phase 7 measures go through the existing validate → generate → execute pipeline. |

---

## Architecture decisions (locked for Phase 7.1)

These resolve open items in [`phase-7-changes.md`](phase-7-changes.md) (resolved decisions section).

| # | Topic | Decision | Rationale |
|---|--------|----------|-----------|
| D1 | `dim_customer` naming | Keep `customer_name` as the legal / canonical display and matching key; add nullable `customer_name_common` `VARCHAR(255)`. Backfill: `customer_name_common = customer_name` where null. | Additive migration; no rename of `customer_name` (avoids churn in loaders, APIs, and tests). |
| D2 | Excel row pairs (value vs delta) | Ingest only value rows for `fact_revenue` in the EUROPE Weekly Commercial v1 profile; skip paired delta rows during parse/classification. MoM and comparisons are computed in application or analytics from facts, not double-stored. | Prevents double-loading revenue; keeps idempotency aligned with Story 7.5 and architect rules. |
| D3 | Fail-whole-file | Default unchanged: template-based uploads use the same transactional fail-whole-file behavior as Phase 1 for a given ingest entry point. Row-level partial success is a separate ingest mode with explicit PO and architect sign-off. | Preserves Phase 1 spirit; avoids silent partial success. |
| D4 | Variance idempotency | One open case per natural key: `(tenant_id, rule_id, customer_id, period_month, division_id)` (adjust if product rules require BU-only scope—document in migration). | Prevents duplicate cases on rerun of detection job. |
| D5 | Explanations and audit | Persist explanations in `revenue_variance_explanation`; emit `audit_event` (or equivalent action codes) for create/update so Phase 6 audit export and compliance narratives stay coherent. | Reuses Phase 6 audit story. |
| D6 | Email and deep links | Queue via `notification_outbox` (or equivalent); store hashed or opaque token reference—never raw long-lived secrets in DB; link resolves for authenticated tenant users where possible, with TTL and single-use policy per security review. | Matches Phase 6 identity expectations (verified recipients). |
| D7 | “Delivery manager” | Resolve to `users` rows in the tenant directory; map via role and/or `user_permission` / org assignment—exact mapping is product and tech lead detail (no silent send to non-directory emails). | Aligns with Story 7.3. |

---

## Data model — implementation order

Order matters: extend dimensions first, then variance and notifications, then template metadata used by ingestion.

1. **Alembic:** add `dim_customer.customer_name_common` (plus backfill).
2. **Alembic:** `variance_detection_rule`, `revenue_variance_case`, `revenue_variance_explanation` (FKs to `tenants`, `users`, hierarchy dims as needed).
3. **Alembic:** `workbook_template_version` (published template registry for `europe_weekly_commercial_v1` and future versions; optional `tenant_id`, NULL = platform-wide for the deploy).
4. **Alembic:** `notification_outbox` (email queue).
5. **RLS:** `ENABLE ROW LEVEL SECURITY` and tenant policies mirroring `fact_revenue` scope for Phase 7 tables listed in [`database-schema.md`](database-schema.md).
6. **ORM:** `app/models/`—new modules or focused files; follow existing `Mapped[]` style.

**Indexes (minimum):** `(tenant_id, status, created_at)` on cases; `(tenant_id, customer_id, period_month)` for lookups; FK indexes per project convention.

---

## Services and API (indicative)

| Layer | Responsibility |
|-------|----------------|
| `services/ingestion/` | New template profile (column map, header detection, value-row-only classification); optional `template_version` on upload metadata. |
| `services/variance/` (new) | Rule evaluation (post-import and scheduled), case upsert, explanation writes, idempotency. |
| `services/notifications/` (new) | Outbox consumer → email provider; deep-link URL builder; retries. |
| `api/v1/` | Matrix and comparison endpoints (reuse `services/analytics/` for numbers—single definition of revenue per `guidelines-for-tech-lead.md` §11a); variance CRUD and explain routes. |

**Indicative routes** (finalize in OpenAPI / `api-contracts.md`):

- `GET` customer matrix / comparison—parameters: org, BU, division, period range; response includes direction for UI (Story 7.4).
- `GET` `/variance/cases`—filtered list and pagination.
- `POST` `/variance/cases/{id}/explanation`—explanation body and optional category.
- `GET` workbook template metadata—current version and document hash for Finance alignment.

Existing `GET /revenue`, `/analytics/*`, `/ingest/*`, Phase 3 `/query`, Phase 4–6 routes must keep working with Phase 7 disabled via flag.

---

## Feature flag

Use **`ENABLE_PHASE7`** (backend) and **`VITE_ENABLE_PHASE7`** (frontend) to gate matrix endpoints, manual cell overrides, and delivery-manager APIs; when off, Phases 1–6 behavior is unchanged.

---

## UX/UI handoff (Stories 7.1–7.5)

Design for clarity and trust: hierarchy through typography and spacing, one accent for primary actions, no color-only status (pair with text or pattern). See project UX rules in `.cursor/rules/ux-ui-designer.mdc`.

| Story | UX focus |
|-------|----------|
| 7.1–7.2 | Customer matrix and comparisons: filters match Phase 2 rollup semantics; child totals reconcile to parent; empty and missing states explicit. |
| 7.3 | Explanation capture: movement (up/down/flat) and text; show who and when for auditors. |
| 7.4 | Green/red not color-only—pair with text, icon, or pattern; restraint on chrome (avoid dashboard noise). |
| 7.5 | Import/export: show template name and version on success; errors row/column actionable. |

**Reference file:** `Sheet1`—row 2 headers; 13 month columns; dual Customer Name columns map to legal and common in DB.

---

## QA handoff

### Regression (must pass unchanged)

- Phase 1 Excel ingest (non-template files), overlap, replace.
- Phase 2 analytics, BU scoping, rollups.
- Phase 3 NL query and audit log (role gates).
- Phase 4 HubSpot paths (if enabled).
- Phase 5 FX, forecast, segments (if enabled).
- Phase 6 SSO, audit export, admin operations.

### New coverage (Phase 7)

- Template import: only value rows land as facts; no duplicate amounts from delta rows.
- Variance: rule fires → case created → email queued (integration test with provider mock) → explanation → `audit_event` present.
- Deep link: expired or invalid token rejected; cross-tenant access denied.
- Matrix API: totals match analytics service for same filters.

---

## References

| Document | Use |
|----------|-----|
| [`phase-7-requirements.md`](../requirements/phase-7-requirements.md) | Locked stories and acceptance criteria |
| [`phase-7-changes.md`](phase-7-changes.md) | Detailed delta vs Phase 6 |
| [`database-schema.md`](database-schema.md) | Table definitions |
| [`guidelines-for-tech-lead.md`](guidelines-for-tech-lead.md) §11f | Coding rules for Phase 7 |
| [`api-contracts.md`](api-contracts.md) | Extend with Phase 7 routes when implemented |

---

## Revision history

| Date | Change |
|------|--------|
| 8 April 2026 | Initial handoff: decisions D1–D7, regression scope, role split for TL / UX / QA. |
