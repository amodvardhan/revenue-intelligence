# Phase [1+1] (Phase 2) validation and QA sign-off

| Field | Value |
|--------|--------|
| **Document file** | `docs/qa/phase-2-report.md` (this file) — Phase [1+1] / Phase 2 QA sign-off (same scope as [`phase-2-requirements.md`](../requirements/phase-2-requirements.md)). Alias: `phase-1+1-report.md` if renamed for naming consistency. |
| **Aligned to** | [`docs/requirements/phase-2-requirements.md`](../requirements/phase-2-requirements.md) (Phase [1+1]; there is no separate `phase-[1+1]-requirements.md` in-repo — see [`docs/design/component-specs.md`](../design/component-specs.md)), [`.cursor/rules/quality-analyst.mdc`](../../.cursor/rules/quality-analyst.mdc) |
| **Last validated** | **3 April 2026** |
| **Legend** | `[x]` Done · `[ ]` Not done · `N/A` Out of scope per PRD |

---

## Executive recommendation

| Verdict | **GO** |
|---------|--------|
| **Rationale** | Full **Phase 1 + Phase 2** automated regression suite is **green** (**60** tests). **Phase 2** user stories **2.1–2.4** acceptance criteria are mapped to **integration + unit tests** (see matrix below). **Frontend** `npm run build` **succeeds**. **Tech Lead** touchpoints (analytics API, revenue drill-down filters, ingestion refresh hook, `/auth/me` BU scope) **regressed** via tests + build. |
| **Release debt** | `pytest --cov=app/services` remains **~73%** (whole `app/services` tree; ingestion/loader dominate misses). **Mitigations applied:** unit tests for analytics helpers (`test_analytics_service_helpers.py`); ingestion overlap E2E asserts `analytics_refresh_metadata` after successful load; compare API returns `percent_change: null` when a leg is missing (no false precision). **≥80%** gate: still obtain **written waiver** or add further branch tests if policy is strict. |

---

## 1. Requirements source

- **Primary:** [`phase-2-requirements.md`](../requirements/phase-2-requirements.md) — Stories **2.1** (hierarchy rollups + BU scoping), **2.2** (period-over-period + explicit periods / missing-leg semantics), **2.3** (filters + drill-down reconciliation to facts), **2.4** (freshness / refresh transparency).
- **Architecture delta:** [`phase-2-changes.md`](../architecture/phase-2-changes.md) — routes under `/api/v1/analytics/...`, `GET /me` extension, ingestion → MV refresh.

---

## 2. Automation executed

```bash
cd backend && pytest tests/ -v --cov=app --cov=app/services --cov-report=term-missing
```

**Result (post-remediation):** **60 passed** (Postgres required; see `backend/tests/conftest.py`).

**Coverage (informative):** Total `app` **~76%**; `app/services` **~73%** (ingestion services remain strong; `app/services/analytics/service.py` has large branching — integration tests exercise primary paths).

**Frontend:**

```bash
cd frontend && npm run build
```

**Result:** **Success** (TypeScript + Vite production build).

---

## 3. Phase 1 regression (unchanged baseline)

| Area | Evidence |
|------|----------|
| Validator, golden aggregate, overlap, large validate | Unit tests **unchanged**, **pass** |
| Revenue API auth / org scope | `test_revenue_api.py` — **pass** |
| Ingest E2E, loader, soft-delete, uniqueness, ingest auth | Integration tests — **pass** |
| Health, `/auth/me`, batch 404 | `test_api_smoke.py` — **pass**; **`business_unit_scope`** on `/me` exercised |

---

## 4. Phase [1+1] acceptance criteria → tests

### Story 2.1 — Aggregate revenue by org hierarchy

| Acceptance criterion | Automated test | Status |
|------------------------|------------------|--------|
| Child totals sum to parent for same period | `test_story_2_1_org_rollup_equals_sum_of_bu_children` | `[x]` |
| Changing hierarchy scope updates results deterministically | Existing `test_rollup_org` / `test_rollup_bu` / `test_rollup_division` + new reconciliation tests | `[x]` |
| Displayed amounts match database-derived aggregates | `test_story_2_1_rollup_amounts_match_revenue_list_total` | `[x]` |
| Row-level BU access for analytics | `test_story_2_1_bu_scope_org_rollup_excludes_other_bus`; `test_bu_restricted_scope_hides_facts` (`GET /revenue`) | `[x]` |

### Story 2.2 — Period-over-period comparisons

| Acceptance criterion | Automated test | Status |
|------------------------|------------------|--------|
| Explicit period boundaries (API contract for labeled presets) | `test_story_2_2_compare_includes_explicit_period_boundaries` | `[x]` |
| Missing data for one leg not implied as zero | `test_story_2_2_missing_current_period_not_implied_zero`; `test_compare_division_hierarchy` (`comparison_missing`) | `[x]` |
| Same definition of revenue as Story 2.1 | Shared `revenue_rollup` / `revenue_compare` service + reconciliation tests above | `[x]` |

**UI-only:** “Period pickers / no ambiguous ‘last quarter’ without confirmation” — **`AnalyticsPage`** documents explicit date-only ranges, links to **Revenue** for drill-down, empty states, and MoM/QoQ/YoY copy clarifying that **exact** from/to fields drive the query (no hidden presets). Browser E2E still optional — `[x]` product UI · `[ ]` automated E2E only |

### Story 2.3 — Filtering and drill-down

| Acceptance criterion | Automated test | Status |
|------------------------|------------------|--------|
| Drill-down ties to `fact_revenue` and reconciles to rollup | `test_story_2_3_drill_down_reconciles_rollup_to_fact_list` | `[x]` |
| Filters combine predictably (AND across dimensions in service) | `test_story_2_3_combined_filters_business_unit_and_dates`; `test_rollup_with_revenue_type_filter_no_match` | `[x]` |
| Interactive performance / async progress | **N/A** for API-only gate; PRD NFR — not load-tested in this run | `N/A` |

### Story 2.4 — Performance via precomputed structures

| Acceptance criterion | Automated test | Status |
|------------------------|------------------|--------|
| Refresh strategy and user-visible freshness | `test_story_2_4_freshness_contract_documents_refresh_and_tenant`; `test_freshness`; OpenAPI + `GET /analytics/freshness` `notes` field | `[x]` |
| No misstatement as “live” without qualification | `as_of` on rollup/compare payloads; freshness `notes` text | `[x]` (API contract) |
| Operational clarity (refresh vs ingest failures) | `test_run_ingestion_overlap_raises_without_replace` asserts **`analytics_refresh_metadata`** rows exist (e.g. `mv_revenue_monthly_by_org`) after first successful `run_ingestion` in the overlap scenario | `[x]` |

---

## 5. Regression — Tech Lead touchpoints

| Component | Change class | Verification |
|-----------|----------------|--------------|
| `app/api/v1/analytics.py` | New rollup / compare / freshness | Integration tests + `test_analytics_endpoints_require_auth` |
| `app/services/analytics/service.py` | Rollup + compare logic | Story 2.x tests above |
| `app/services/analytics/refresh.py` | Post-ingest MV refresh | Ingestion overlap integration test asserts metadata after completed batch; refresh file **~86%** covered |
| `app/api/v1/revenue.py` | Drill-down filters + BU scope | Reconciliation + BU tests |
| `app/services/ingestion/ingestion_service.py` | Calls `refresh_analytics_structures` | Phase 1 ingest E2E **pass** |
| `app/main.py` | Mounts analytics router | Import smoke via all route tests |
| Frontend (`AnalyticsPage`, routing, API client) | Phase 2 UI | `npm run build` **OK** |

---

## 6. Known gaps (non-blocking unless policy says otherwise)

| Gap | Severity | Notes |
|-----|----------|--------|
| `app/services` **~73%** vs **80%** historical target | Medium (process) | Partially addressed with `test_analytics_service_helpers.py`; remaining gap is mostly **ingestion/loader** branches. Obtain **waiver** or extend branch tests if policy requires **≥80%** on the whole package. |
| Browser E2E for Analytics UI | Low (scope) | Optional Playwright/Cypress — Story 2.2 UI AC implemented in `AnalyticsPage`. |
| ~~MV refresh proof after ingest~~ | — | **Closed:** `analytics_refresh_metadata` asserted in `test_run_ingestion_overlap_raises_without_replace`. |

### QA remediation (engineering follow-up to this report)

| Item | Action taken |
|------|----------------|
| Story 2.2 UI — explicit periods | `AnalyticsPage`: banner + labels (“Rollup from/to”), compare helper copy, **Revenue** link (no raw REST names in hero). |
| Story 2.2 — missing leg vs % | `revenue_compare`: `percent_change` is **`null`** when either leg is missing; UI shows **—**; `test_story_2_2_missing_current_period_not_implied_zero` asserts `percent_change is None`. |
| Story 2.4 — refresh proof | Overlap ingestion test queries **`AnalyticsRefreshMetadata`** after first successful load. |
| Coverage / helpers | `tests/unit/test_analytics_service_helpers.py` exercises `_amount_str`, `_pct_str`, `_resolve_org_scope`, `_period_label`. |
| Empty states | Rollup/compare tables show **no-data** copy when `rows` is empty. |

---

## 7. Sign-off

| Role | Status |
|------|--------|
| **Quality Analyst (automation)** | **`[x]` GO** — criteria in Section 4 satisfied by automated tests where applicable; Section 6 gaps documented. |

---

## Revision history

| Date | Change |
|------|--------|
| 3 April 2026 | Initial Phase [1+1] / Phase 2 report: 52 tests, Phase 2 AC matrix, Tech Lead regression table, GO with coverage debt. |
| 3 April 2026 | **Filename:** canonical QA report is `phase-1+1-report.md` (Phase [1+1]); supersedes temporary `phase-2-report.md`. |
| 3 April 2026 | **Remediation:** 60 tests; ingestion→metadata assert; analytics helper unit tests; compare `percent_change` null semantics; `AnalyticsPage` UX fixes; Section 6 gaps updated. |
