# Phase 5 Architecture Delta (vs Phase 4)

**Status:** APPROVED (architecture alignment)  
**Aligned to:** [`docs/requirements/phase-5-requirements.md`](../requirements/phase-5-requirements.md) (Product Owner approval **6 April 2026** — requirements **LOCKED**)  
**Purpose:** Single place listing **what Phase 5 adds** versus **what already exists** from Phase 4, **open architect decisions** from the requirements doc, and **risks to Phase 4 (and earlier phases)**.

---

## 1. Already exists (Phase 4 — unchanged baseline)

| Area | What exists |
|------|-------------|
| **HubSpot path** | OAuth, incremental sync, `integration_sync_run`, mapping exceptions, `revenue_source_conflict`, `GET /analytics/revenue/source-reconciliation` |
| **Facts** | `fact_revenue` with `source_system` (`excel` \| `hubspot`), `source_metadata`, idempotency `(source_system, external_id)` |
| **Authority** | Excel booked actuals **not** silently overwritten by HubSpot; conflicts surfaced — PRD §5 decision 5 |
| **Analytics / NL** | Phase 2 rollups/compare; Phase 3 NL + `query_audit_log`; semantic version traceability |
| **Multi-currency (minimal)** | `fact_revenue.currency_code` + `tenants.default_currency_code` — **no** FX table before Phase 5 |

Phase 4 **did not** ship forecast facts, cost facts, FX rate management, segment definitions, profitability APIs, or reporting-currency consolidation with rate lineage.

---

## 2. New in Phase 5 (schema)

| Object | Purpose |
|--------|---------|
| **`fx_rate`** | Manual FX table: pair, **effective_date**, **NUMERIC** rate, **rate_source** label (v1: manual upload) — Story 5.4; PRD §5 decision 7. |
| **`forecast_series`** | Versioned forecast run: **imported** vs **statistical**, scenario, **methodology** JSON, supersede chain — Story 5.1. |
| **`fact_forecast`** | Forward-looking amounts only — **separate** from `fact_revenue`; idempotent keys per series — Story 5.1. |
| **`fact_cost`** | Cost lines at agreed grain; **NUMERIC**; `cost_category` / source — Story 5.2. |
| **`cost_allocation_rule`** | Versioned allocation basis and **rule_definition** JSON; effective dating — Story 5.2. |
| **`segment_definition`** | **Replayable** rules (`rule_definition` JSON), optional `owner_org_id`, version bump — Story 5.3. |
| **`segment_membership`** | Persisted membership by period or **as-of** — Story 5.3. |
| **`fact_revenue` (optional columns)** | **`amount_reporting_currency`**, **`fx_rate_id`** — only if product caches converted amounts at ingest or layered persistence; otherwise **NULL** and conversion at **report time** only. |

**Reuse:** `ingestion_batch` for forecast, cost, and FX file loads via `source_system` values (e.g. `forecast_excel`, `cost_excel`, `fx_upload`). **`tenants.default_currency_code`** is the **reporting currency** for consolidation (PRD §5 decision 7).

---

## 3. New in Phase 5 (services & modules)

| Piece | Role |
|-------|------|
| **`services/fx/`** | Rate lookup, conversion helper(s), validation that rate exists for period/pair; **no silent fallback**. |
| **`services/forecast/`** | Series lifecycle, optional **statistical** baseline job, linkage to ingest pipeline. |
| **`services/profitability/`** | Join `fact_revenue` + `fact_cost` + allocations; **same filter semantics** as analytics for revenue leg. |
| **`services/segments/`** | Evaluate `rule_definition`, write `segment_membership`, enforce org/BU access on customer scope. |
| **`services/analytics/` (extend)** | `GET /analytics/revenue/consolidated`, `GET /analytics/profitability/summary`, `GET /analytics/revenue/forecast-vs-actual` — documented rounding and **actual vs forecast** separation. |
| **`services/query_engine/` (extend)** | New governed measures (forecast, margin, segment, FX-adjusted); **validator** allowlists; optional **new audit** semantics for FX-sensitive queries — **no** raw LLM SQL. |
| **`tasks/`** | Celery jobs for statistical forecast refresh, segment materialization, optional MV refresh after rate uploads. |

---

## 4. New in Phase 5 (HTTP API)

All under `/api/v1` — see `api-contracts.md` §10.

| Method | Path | Stories |
|--------|------|---------|
| `GET` | `/tenant/settings` | 5.4 |
| `PATCH` | `/tenant/settings` | 5.4 |
| `GET` | `/fx-rates` | 5.4 |
| `POST` | `/fx-rates/uploads` | 5.4 |
| `GET` | `/forecast/series` | 5.1 |
| `GET` | `/forecast/series/{forecast_series_id}` | 5.1 |
| `POST` | `/ingest/forecast-uploads` | 5.1 |
| `GET` | `/forecast/facts` | 5.1 |
| `POST` | `/forecast/series/{forecast_series_id}/statistical-refresh` | 5.1 |
| `POST` | `/ingest/cost-uploads` | 5.2 |
| `GET` | `/costs/facts` | 5.2 |
| `GET` | `/costs/allocation-rules` | 5.2 |
| `POST` | `/costs/allocation-rules` | 5.2 |
| `GET` | `/analytics/profitability/summary` | 5.2 |
| `GET` | `/segments/definitions` | 5.3 |
| `POST` | `/segments/definitions` | 5.3 |
| `PATCH` | `/segments/definitions/{segment_id}` | 5.3 |
| `POST` | `/segments/definitions/{segment_id}/materialize` | 5.3 |
| `GET` | `/segments/definitions/{segment_id}/membership` | 5.3 |
| `GET` | `/analytics/revenue/consolidated` | 5.4 |
| `GET` | `/analytics/revenue/forecast-vs-actual` | 5.1 |

**Note:** `GET /tenant/settings` may be merged into `GET /me` — document one canonical approach in OpenAPI.

**Out of scope v1:** External **FX rate API** (PRD §5 decision 7) unless change request.

---

## 5. Explicitly out of scope (Phase 5 requirements)

Per [`phase-5-requirements.md`](../requirements/phase-5-requirements.md):

- **General ledger** as system of record; **tax / statutory** filings from this product.  
- **Real-time streaming** from all enterprise systems.  
- **Full EPM replacement**; **new CRMs** beyond HubSpot; **bidirectional CRM writeback** (unless separate initiative).  
- **Optional rate API** for FX until manual path is complete and PO pulls it forward.

---

## 6. Open architect decisions (from Phase 5 requirements)

Resolved in design review before implementation freeze (see requirements §“Decisions that need architect input”):

1. **Schema** — Final uniqueness constraints on `fx_rate` if multiple scenarios; **exact** `segment_membership` unique key for period vs as-of.  
2. **Forecast storage** — How imported files bind to **periods**, **scenarios**, immutability; how **statistical** baselines refresh and whether they persist as new `forecast_series` rows.  
3. **Profitability grain** — Join model `fact_revenue` ↔ `fact_cost`; **partial periods** and **cross-BU** allocations.  
4. **Multi-currency application order** — Ingest-time vs report-time vs **layered**; impact on **Phase 2 materialized views** and refresh when rates **change** (historical restatement in v1 — PO open question 9).  
5. **Segmentation engine** — Rule encoding in `rule_definition`; **materialized** vs on-the-fly; performance targets (parent PRD §4).  
6. **NL + semantic layer** — New measures and **audit** event types; **disambiguation** when user mixes forecast and actuals.  
7. **Double-counting** — API and NL defaults: **actuals-only** for “revenue” unless user selects forecast or **explicit** combined endpoint — Phase 4 CRM vs Excel rules **carry forward**.

---

## 7. Phase 4 regression / breakage risks

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| **MVs vs FX** | Phase 2 **`mv_revenue_*`** are **native-currency** sums today. Reporting-currency dashboards need **either** new MVs + refresh on rate change **or** **on-the-fly** conversion — otherwise **wrong** consolidated totals. | Architect **one** strategy; extend `analytics_refresh_metadata` for FX-dependent structures; document `as_of`. |
| **HubSpot sync + FX** | After Phase 5, **`fact_revenue`** may include **multi-currency** rows; rollup without conversion **mixes** currencies incorrectly. | `GET /analytics/revenue/rollup` behavior must be **documented**: native only until consolidation endpoint, or **require** reporting currency in Phase 5 UI for org-wide views. |
| **Conflict detection vs FX** | `revenue_source_conflict` compares **amounts** in potentially **different currencies** if not normalized — **false** variances. | Reconciliation logic **must** compare **like-for-like** (same currency or both converted at same rate date) — extend conflict pipeline in design. |
| **NL “total revenue”** | Phase 4 risk (Excel vs HubSpot) **worsens** if NL **adds** forecast or FX-adjusted without disambiguation. | Semantic layer **defaults** to **booked actuals** with explicit **measure** and **source**; Phase 5 measures require **clarification** on ambiguity (Phase 3 patterns). |
| **`ENABLE_PHASE5` off** | Phase 4 HubSpot, reconciliation APIs, and Excel ingest **must** work unchanged. | Feature flags per `guidelines-for-tech-lead.md` §11d; no **required** FK from Phase 4-only code paths to new tables. |
| **Rate upload mistakes** | Wrong manual rate **restates** consolidated history if cached on facts. | Prefer **report-time** conversion for v1 **or** immutable rate rows + explicit **re-run** job; align with PO open question 9. |
| **Performance** | Segment materialization + profitability joins on large `fact_revenue` **compete** with HubSpot sync and NL. | Timeouts, async jobs, indexes on new tables; **do not** block `integration_sync_run` on segment jobs. |

**When all Phase 5 feature flags are off:** Phase 4 behavior (including **`GET /integrations/hubspot/*`**, **`GET /analytics/revenue/source-reconciliation`**, **`revenue_source_conflict`**) **shall** match Phase 4 QA baseline aside from **additive** nullable columns on `fact_revenue` (ignored when unset).

---

## 8. Related documents

- `docs/architecture/architecture-overview.md`  
- `docs/architecture/database-schema.md` — §3.10 (optional columns), §3.23–§3.29, §10  
- `docs/architecture/api-contracts.md` — §10–§13 (Phase 5 contracts + Phase 6+ appendices)  
- `docs/architecture/guidelines-for-tech-lead.md` — §11d  
- `docs/architecture/phase-6-changes.md` — governance layer after Phase 5  

---

**Status:** APPROVED (architecture alignment) · **2026-04-06** — Delta vs Phase 4 for enterprise intelligence expansion. Implementation must follow locked requirements; material changes require Product Owner **change request** per `phase-5-requirements.md`.
