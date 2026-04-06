# Phase 3 Architecture Delta (vs Phase 2)

**Status:** APPROVED (architecture alignment)  
**Aligned to:** [`docs/requirements/phase-3-requirements.md`](../requirements/phase-3-requirements.md) (APPROVED 6 April 2026)  
**Purpose:** Single place listing **what Phase 3 adds** versus **what already exists** from Phase 2, **open architect decisions** from the requirements doc, and **risks to Phase 2 behavior**.

**Filename note:** This follows the same convention as `phase-2-changes.md` (Phase *N* → `phase-N-changes.md`). It is **not** `phase-4-changes.md`.

---

## 1. Already exists (Phase 2 — unchanged baseline)

| Area | What exists |
|------|-------------|
| **Canonical model** | All Phase 1 tables plus `user_business_unit_access`, `analytics_refresh_metadata`, materialized views (or equivalent) per `database-schema.md` §7 |
| **Ingestion** | Same Excel pipeline, overlap/replace, Celery |
| **Fact & dimensions** | `GET /revenue`, dimension list APIs |
| **Analytics** | `GET /analytics/revenue/rollup`, `GET /analytics/revenue/compare`, `GET /analytics/freshness` — BU scoping, `as_of`, drill-down via `GET /revenue` |
| **Auth** | `GET /me` with `business_unit_scope` |
| **Architecture diagram** | `architecture-overview.md` already shows **Semantic layer loader**, **Query engine**, **QE → OAI**, **QE → PG** — Phase 3 **implements** that path |

Phase 2 **did not** ship production NL UX, governed semantic persistence, disambiguation flows, or NL audit APIs.

---

## 2. New in Phase 3 (schema)

| Object | Purpose |
|--------|---------|
| **`semantic_layer_version`** | Which governed semantic bundle is active per tenant; version label, artifact id, `content_sha256` for traceability (Story 3.1). |
| **`semantic_term_mapping`** | Optional DB mirror of synonym → canonical keys (`metric` / `dimension` / etc.) bound to a version — may be omitted if YAML-only with version pointer only. |
| **`nl_query_session`** | Server-side clarification state (opaque token hash, `pending_context`, TTL) — **optional** if implementation uses stateless signed tokens only. |
| **`query_audit_log` (columns)** | Extended: `correlation_id`, `nl_session_id`, `semantic_version_id`; `resolved_plan` holds **final** interpretation after clarification (Stories 3.3–3.4). |

Existing `query_audit_log` table from the **pre–Phase 3** schema doc is **expanded** — migrations must be **additive** for any Phase 2 deployment that already created a slimmer `query_audit_log` stub.

---

## 3. New in Phase 3 (services & modules)

| Piece | Role |
|-------|------|
| **`core/semantic_layer.py`** | Load / validate semantic artifacts; bind to `semantic_layer_version`. |
| **`services/query_engine/`** | NL → structured plan → validator → safe execution (read-only, limits); OpenAI client **only** via `settings.OPENAI_MODEL`. |
| **Optional reuse** | Call **`services/analytics/`** for aggregates instead of duplicate SQL (reconciliation with Story 2.x). |
| **Readonly / RLS** | NL execution uses same `app.tenant_id` / `app.user_id` session vars as analytics; optional **readonly DB role** for NL path only. |

---

## 4. New in Phase 3 (HTTP API)

All under `/api/v1` — see `api-contracts.md` §8.

| Method | Path | Stories |
|--------|------|---------|
| `POST` | `/query/natural-language` | 3.1–3.3 (initial + clarification follow-up in one contract) |
| `GET` | `/query/audit` | 3.4 |
| `GET` | `/query/audit/{log_id}` | 3.4 |
| `GET` | `/semantic-layer/version` | 3.1 (optional governance read) |

**Disambiguation:** Clarification **continues** via `POST /query/natural-language` with `disambiguation_token` + `clarifications` — no separate path required unless implementation prefers a dedicated route (then document in OpenAPI).

---

## 5. Explicitly out of scope (Phase 3 requirements)

- **HubSpot / live CRM** as source of truth (Phase 4).
- **New analytics metrics** beyond exposing existing Phase 2 capabilities through NL (thin NL).
- **Forecasting, multi-currency, advanced segmentation** (Phase 5).
- **Full enterprise SSO** as a gate (unless change request).
- **Customer-facing MCP** — confirm with PO/architect before shipping; must not bypass Story 3.2 validation if added.

---

## 6. Open architect decisions (from Phase 3 requirements)

These remain **design choices** for implementation review; they do not override locked scope:

1. **Semantic layer shape** — DB + YAML hybrid vs repo-only; how versions roll forward.
2. **Execution strategy** — Generated safe SQL vs structured calls into analytics services — **reconciliation** with Phase 2 APIs is mandatory either way.
3. **Safety envelope** — Exact allowlist, max rows, statement timeout, readonly role.
4. **LLM integration** — Sync vs async UX, timeouts, rate limits, provider failure handling.
5. **Audit persistence** — PII handling for `natural_query`; correlation id propagation.
6. **MCP (optional)** — Server boundaries and auth if Python MCP SDK is in scope.

---

## 7. Phase 2 regression / breakage risks

| Risk | Mitigation |
|------|------------|
| **Reconciliation drift** | If NL uses ad-hoc SQL instead of shared analytics/revenue logic, **numbers can disagree** with `GET /analytics/*` and `GET /revenue` — **mandatory** shared service layer or identical query definitions. |
| **RLS / BU scope** | NL query execution must apply **the same** org/BU rules as Phase 2; otherwise users see **different** rows than the Analytics UI. |
| **Resource contention** | Heavy NL + LLM calls could **slow** API workers shared with ingestion/analytics — isolate timeouts, consider queue/async for NL if needed. |
| **MV lag vs NL answers** | If NL hits **raw facts** while UI shows **materialized** rollups, transient **mismatch** until refresh — align NL path with documented freshness (same as Story 2.4 semantics) or document dual behavior. |
| **Schema migration** | Adding `query_audit_log` columns or new RLS policies must **not** break existing analytics/ingest migrations — test Phase 2 smoke after Alembic upgrade. |
| **`ENABLE_NL_QUERY=false`** | Phase 2 **must** keep working when NL is disabled — no required dependency from analytics routes to OpenAI. |

---

## 8. Related documents

- `docs/architecture/architecture-overview.md`  
- `docs/architecture/database-schema.md` — §3.12–§3.15  
- `docs/architecture/api-contracts.md` — §8+ (NL §8; later phases §9–§13)  
- `docs/architecture/guidelines-for-tech-lead.md` — §7, §11b  

---

**Status:** APPROVED (architecture alignment) · **2026-04-06** — Delta vs Phase 2 baseline for NL query phase.
