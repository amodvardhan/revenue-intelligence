# Phase 4 Architecture Delta (vs Phase 3)

**Status:** APPROVED (architecture alignment)  
**Aligned to:** [`docs/requirements/phase-4-requirements.md`](../requirements/phase-4-requirements.md) (Product Owner approval for execution baseline)  
**Purpose:** Single place listing **what Phase 4 adds** versus **what already exists** from Phase 3, **open architect decisions** from the requirements doc, and **risks to Phase 3 (and Phase 2) behavior**.

---

## 1. Already exists (Phase 3 — unchanged baseline)

| Area | What exists |
|------|-------------|
| **Canonical model** | All prior tables through `query_audit_log`, `semantic_layer_version`, `semantic_term_mapping`, `nl_query_session` per `database-schema.md` |
| **Excel ingestion** | `POST /ingest/uploads`, batches, overlap/replace, Celery ingest tasks |
| **Facts** | `GET /revenue` with `source_system` (Excel today) |
| **Analytics** | Rollup, compare, freshness — Phase 2 semantics |
| **NL query** | `POST /query/natural-language`, audit APIs, semantic version read |
| **Auth / RLS** | JWT, BU scoping, tenant isolation |

Phase 3 **did not** ship HubSpot OAuth, CRM sync workers, mapping-exception workflows, or Excel-vs-HubSpot reconciliation APIs.

---

## 2. New in Phase 4 (schema)

| Object | Purpose |
|--------|---------|
| **`hubspot_connection`** | OAuth connection health, encrypted token storage pointer, portal id, `status` for UI (Stories 4.1). |
| **`hubspot_sync_cursor`** | Incremental sync watermark per `object_type` (v1: deals) — Story 4.2. |
| **`hubspot_id_mapping`** | Configurable HubSpot object id → `dim_customer` / org (Story 4.3). |
| **`integration_sync_run`** | Audit of sync jobs: trigger, counts, errors, `correlation_id` (Stories 4.2, parent PRD §4). |
| **`revenue_source_conflict`** | Surfaces Excel vs HubSpot collisions — **no silent overwrite** of Finance actuals (Story 4.3; PRD §5 decision 5). |
| **`hubspot_deal_staging`** | **Optional** raw JSON staging before `fact_revenue` — forensics / repair (Story 4.2). |
| **`fact_revenue.source_metadata`** | Optional JSONB for CRM pipeline/stage context on HubSpot rows (additive column). |

**Reuse:** `ingestion_batch.source_system` already allows `'hubspot'`; sync loads may create batches for lineage. **`fact_revenue`** receives HubSpot rows with `source_system = 'hubspot'` and **globally unique** `(source_system, external_id)` per deal id.

---

## 3. New in Phase 4 (services & modules)

| Piece | Role |
|-------|------|
| **`services/integrations/hubspot/`** (or equivalent package) | OAuth flow helpers, HubSpot API client (rate limits, 429 backoff), deal → canonical mapping, conflict detection. |
| **`tasks/sync_tasks.py`** | Celery entrypoints for scheduled and manual sync; idempotent writes; updates `integration_sync_run` + cursors. |
| **Analytics reconciliation** | Shared aggregation helpers for **`GET /analytics/revenue/source-reconciliation`** — same numeric discipline as Phase 2 (`NUMERIC`, filters). |
| **Optional:** extend **`query_engine`** | Thin inclusion of CRM-sourced facts in NL/analytics with explicit **source** filters or measures — **no** speculative semantic expansion beyond Phase 4 requirements. |

---

## 4. New in Phase 4 (HTTP API)

All under `/api/v1` — see `api-contracts.md` §9.

| Method | Path | Stories |
|--------|------|---------|
| `GET` | `/integrations/hubspot/oauth/authorize-url` | 4.1 |
| `GET` | `/integrations/hubspot/oauth/callback` | 4.1 |
| `GET` | `/integrations/hubspot/status` | 4.1 |
| `POST` | `/integrations/hubspot/disconnect` | 4.1 |
| `POST` | `/integrations/hubspot/sync` | 4.2 |
| `GET` | `/integrations/hubspot/sync-runs` | 4.2 |
| `GET` | `/integrations/hubspot/sync-runs/{sync_run_id}` | 4.2 |
| `GET` | `/integrations/hubspot/mapping-exceptions` | 4.3 |
| `PATCH` | `/integrations/hubspot/mapping-exceptions/{mapping_id}` | 4.3 |
| `GET` | `/analytics/revenue/source-reconciliation` | 4.3 |
| `GET` | `/integrations/hubspot/revenue-conflicts` | 4.3 |
| `PATCH` | `/integrations/hubspot/revenue-conflicts/{conflict_id}` | 4.3 |

---

## 5. Explicitly out of scope (Phase 4 requirements)

- **Other CRMs** (Salesforce, Dynamics, …) unless a change request.  
- **Bidirectional sync** (write-back to HubSpot) — default ingestion-only.  
- **Full** CPQ/billing/lifecycle — not a full RevOps suite.  
- **Phase 5** pillars (forecasting, multi-currency productization, advanced segmentation) except minimal fields for mapping context.  
- **Large new NL semantics** — thin integration only; align with Phase 3 validator discipline.  
- **Full enterprise SSO** as a Phase 4 gate.

---

## 6. Open architect decisions (from Phase 4 requirements)

Resolved in implementation / design review before code freeze:

1. **HubSpot auth model** — Single app vs per-tenant; refresh rotation; failure handling; vault vs DB encryption.  
2. **Sync architecture** — Celery queues, Beat schedule, idempotency, HubSpot rate limits, **first-run backfill** vs incremental only after.  
3. **Canonical schema** — Staging required or optional; linking `ingestion_batch` ↔ `integration_sync_run`.  
4. **Dedupe and grain** — Business key for deal facts vs Excel facts; upsert; soft-delete when deal removed in HubSpot.  
5. **Conflict detection** — Exact rule for `reconciliation_key` / same canonical key.  
6. **Observability** — Metrics, logs, correlation id end-to-end.  
7. **NL and analytics** — How CRM rows participate in rollups/NL (source filters, labels) without double-counting.

---

## 7. Phase 3 regression / breakage risks

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| **Ambiguous “revenue” in NL** | HubSpot adds **pipeline/CRM** rows alongside Excel **booked actuals** — users may ask “total revenue” and get a **blended** or **wrong** answer. | NL + semantic layer **must** expose **source** or **measure** disambiguation (or default to Excel-only for “booked” terms per PRD). |
| **Double-counting in analytics** | Rollups that **sum all** `fact_revenue` without `source_system` awareness could **mix** Excel and HubSpot for the same business reality. | Phase 2 rollup/compare endpoints need **documented** behavior: filter by source, separate measures, or exclude CRM from “booked” views — **align with** `GET /analytics/revenue/source-reconciliation`. |
| **MV staleness vs HubSpot** | Materialized views may **lag** behind new HubSpot sync while NL hits raw facts — same class of issue as Phase 2 Story 2.4. | Refresh MVs after HubSpot batch completion **or** document `as_of` / freshness for CRM-sourced data. |
| **`UNIQUE (source_system, external_id)` collision** | If HubSpot `external_id` collides with Excel’s scheme accidentally, **facts could merge or conflict** incorrectly. | Enforce **distinct prefixes** / namespaces per source (e.g. HubSpot ids never match `excel:batch:row` pattern). |
| **Query load / worker contention** | Sync + NL + Excel ingest share API and DB — long HubSpot runs could **starve** interactive traffic. | Timeouts, isolated queues, `ENABLE_HUBSPOT` off switch, rate limits. |
| **RLS / role drift** | New integration tables must use **same** `app.tenant_id` session pattern; integration admin routes must **not** leak tokens to `viewer`. | RLS on new tables; strict role checks for OAuth and mapping PATCH. |
| **Phase 3 audit narrative** | `query_audit_log` remains append-only; integration audit is **`integration_sync_run`** — operators need **one** operational story (dashboards or linked correlation ids). | Correlate `correlation_id` across HTTP → Celery → DB. |

**When `ENABLE_HUBSPOT=false`:** Phase 3 NL, query audit, and Phase 2 analytics **must** behave as before — no import-time dependency on HubSpot settings.

---

## 8. Related documents

- `docs/architecture/architecture-overview.md`  
- `docs/architecture/database-schema.md` — §3.10, §3.17–§3.22, §9  
- `docs/architecture/api-contracts.md` — §9+ (HubSpot §9; later phases §10–§13)  
- `docs/architecture/guidelines-for-tech-lead.md` — §6, §11c  

---

**Status:** APPROVED (architecture alignment) · **2026-04-06** — Delta vs Phase 3 baseline for HubSpot integration phase.
