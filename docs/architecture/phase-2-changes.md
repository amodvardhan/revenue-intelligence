# Phase 2 Architecture Delta (vs Phase 1)

**Status:** APPROVED (architecture alignment)  
**Aligned to:** [`docs/requirements/phase-2-requirements.md`](../requirements/phase-2-requirements.md) (APPROVED 3 April 2026)  
**Purpose:** Single place listing **what Phase 2 adds** versus **what already exists** from Phase 1, and **risks to Phase 1 behavior**.

---

## 1. Already exists (Phase 1 — unchanged baseline)

| Area | What exists |
|------|-------------|
| **Canonical model** | `tenants`, `users`, `user_org_role`, `dim_organization`, `dim_business_unit`, `dim_division`, `dim_customer`, `dim_revenue_type`, `ingestion_batch`, `fact_revenue` |
| **Ingestion** | `POST /api/v1/ingest/uploads`, `GET /api/v1/ingest/batches`, `GET /api/v1/ingest/batches/{batch_id}` — fail-whole-file, overlap/replace, Celery for large files |
| **Fact read API** | `GET /api/v1/revenue` — cursor pagination, org-scoped via `user_org_role` |
| **Dimensions** | `GET /api/v1/organizations`, `/business-units`, `/divisions`, `/customers`, `/revenue-types` |
| **Auth** | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `GET /me` |
| **App layering** | FastAPI routers → services → repositories; SQLAlchemy 2 async; Alembic migrations |
| **Diagram** | `architecture-overview.md` already includes **Analytics service** and **Analytics** path to PostgreSQL — Phase 2 **implements** that path |

Phase 1 **did not** ship hierarchy rollups, materialized analytics, PoP comparison APIs, or BU-restrictive access (pilot could be tenant-wide / org-wide via roles only).

---

## 2. New in Phase 2 (schema)

| Object | Purpose |
|--------|---------|
| **`user_business_unit_access`** | Row-level BU scoping when populated; empty set = org-wide access per `user_org_role` (Phase 1–compatible). See `database-schema.md` §3.3a. |
| **`analytics_refresh_metadata`** | Freshness / “as of” per precomputed structure; links to last completed batch when applicable. See `database-schema.md` §3.11. |
| **Materialized views (or equivalent)** | Named in `database-schema.md` §7 — e.g. monthly rollups by org/BU/division; refresh after load or on schedule. |

**RLS:** Phase 2 **tightens** policies from tenant-only to org **+ optional BU** visibility using the new table (see `database-schema.md` §6).

---

## 3. New in Phase 2 (services & jobs)

| Piece | Role |
|-------|------|
| **`services/analytics/`** | Rollup and comparison logic; must reuse the same fact-selection rules as the revenue list API. |
| **MV refresh** | Triggered post-ingest and/or scheduled; updates `analytics_refresh_metadata`. |
| **Optional Celery job** | If refresh is async and long-running, thin task wrapper calling refresh logic (pattern already used for ingest). |

---

## 4. New in Phase 2 (HTTP API)

All under `/api/v1` — see `api-contracts.md` §7.

| Method | Path | Stories |
|--------|------|---------|
| `GET` | `/analytics/revenue/rollup` | 2.1, 2.3 |
| `GET` | `/analytics/revenue/compare` | 2.2 |
| `GET` | `/analytics/freshness` | 2.4 |

**Drill-down:** Reuses **`GET /revenue`** with matching filters (no new endpoint required for baseline).

**`GET /me`:** Response shape **extended** with `business_unit_scope` (Phase 2 clients; backward-compatible if omitted on older servers).

---

## 5. Explicitly still Phase 3+ (not Phase 2)

- Natural language query (`POST /query/natural-language`) — stub only.
- Semantic layer, MCP-driven CXO UX.
- HubSpot / external CRM ingestion.
- Forecasting, multi-currency, full enterprise SSO as default gate.

---

## 6. Open architect decisions (from Phase 2 requirements)

Resolved in implementation design review, not overridden by this delta:

1. MV vs summary table implementation details; **CONCURRENT** refresh vs locking.
2. Exact mapping for facts with `business_unit_id` NULL under BU-restricted users.
3. Fiscal vs calendar periods — extra MVs/columns vs calendar-only v1.
4. Stale-read UX: block until refresh vs serve last aggregates with visible `as_of`.
5. Whether **MoM, QoQ, YoY** all ship in first Phase 2 release.

---

## 7. Phase 1 regression / breakage risks

| Risk | Mitigation |
|------|------------|
| **Stricter RLS / BU scope** | Users who previously saw **all** org or tenant facts may see **fewer** rows after `user_business_unit_access` is populated. Migration: seed access rows deliberately; document pilot behavior. |
| **`GET /revenue` row counts** | Same RLS as analytics — must apply BU rules consistently or totals disagree between list and rollup. |
| **Analytics vs raw facts timing** | After ingest, MVs may lag; `as_of` on analytics responses and `GET /analytics/freshness` must prevent misstating rolled-up numbers as “live” without qualification (Story 2.4). |
| **Replace imports** | Replace deletes/soft-deletes facts and loads new rows; refresh must run before analytics match new truth — document **consistency window** if product allows brief lag (follow-up item in requirements). |
| **`GET /me` contract** | Additive field `business_unit_scope` — existing clients ignoring unknown JSON keys remain safe. |

---

## 8. Related documents

- `docs/architecture/architecture-overview.md`  
- `docs/architecture/database-schema.md`  
- `docs/architecture/api-contracts.md`  
- `docs/architecture/guidelines-for-tech-lead.md` §11a  

---

**Note on filename:** This file summarizes **Phase 2** delivery vs Phase 1. See [`phase-3-changes.md`](phase-3-changes.md) for the Phase 3 delta (NL query, semantic layer, audit) against the Phase 2 baseline.
