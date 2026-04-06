# Phase 5 validation and QA sign-off

| Field | Value |
|--------|--------|
| **Document file** | `docs/qa/phase-5-report.md` (this file) |
| **Aligned to** | [`docs/requirements/phase-5-requirements.md`](../requirements/phase-5-requirements.md), [`.cursor/rules/quality-analyst.mdc`](../../.cursor/rules/quality-analyst.mdc) |
| **Last validated** | **6 April 2026** |
| **Legend** | `[x]` Done · `[ ]` Not done · `N/A` Out of scope per PRD |

---

## Executive recommendation

| Verdict | **GO** (Phase 5 enterprise expansion — backend + semantic; UI spot-check) |
|---------|-----------------------------------------------------------------------------|
| **Rationale** | **Full suite:** **100 passed**, **0 skipped** (~25s). **Phase 1–4 regression** remains green (analytics, ingest, NL query, revenue, smoke, HubSpot, Phase 5 flag). **Phase 5** adds **13** automated tests (**12** integration in `tests/integration/test_phase5_integration.py` + **1** unit for semantic bundle). **Frontend** `npm run build` **succeeds** (Phase 5 pages behind `VITE_ENABLE_PHASE5`). |
| **Tooling note** | Integration tests require **`pytest-asyncio` ≥ 0.24** with **`asyncio_default_fixture_loop_scope = session`** (see `backend/pyproject.toml`). Older **pytest-asyncio 0.23** can raise **“Future attached to a different loop”** on `db_session` setup — upgrade dev deps if you see that. |
| **Residual risk** | **UI disclaimer** (“forecast not audited”) is implemented on **Forecasting** page copy; **full UX review** against PRD is manual. **NL** exposes **`forecast_total`** in `semantic_layer.yaml`; **end-to-end NL** on forecast/margin/segment phrases is **not** fully matrix-tested here (Phase 3 patterns assumed). **Optional FX rate API** remains **out of scope** per PRD. |
| **Release debt** | **`GET /costs/facts`** does not echo **`external_id`** in JSON (reconciliation may use **`cost_fact_id`** + detail paths); consider exposing **`external_id`** in a later patch if Finance asks for source-line IDs in list views. |

---

## 1. Requirements source

- **Primary:** [`phase-5-requirements.md`](../requirements/phase-5-requirements.md) — Stories **5.1** (forecasting), **5.2** (profitability), **5.3** (segments), **5.4** (multi-currency).

---

## 2. Automation executed

```bash
cd backend && pytest tests/ -v --tb=short
```

**Result:** **100 passed**, **0 skipped**. Integration sessions **auto-migrate** to head per [`tests/conftest.py`](../../backend/tests/conftest.py) when integration tests are collected (unless `PYTEST_SKIP_ALEMBIC_UPGRADE` is set).

**New / updated Phase 5 tests:**

- Integration: [`tests/integration/test_phase5_integration.py`](../../backend/tests/integration/test_phase5_integration.py)
- Feature flag (existing): [`tests/integration/test_phase5_flags.py`](../../backend/tests/integration/test_phase5_flags.py)
- Semantic bundle: [`tests/unit/test_semantic_layer_bundle.py`](../../backend/tests/unit/test_semantic_layer_bundle.py) (`test_semantic_bundle_includes_phase5_forecast_metric`)

**Frontend:**

```bash
cd frontend && npm run build
```

**Result:** **Success** (TypeScript + Vite production build).

---

## 3. Phase 1–4 regression (shared components)

| Area | Evidence |
|------|----------|
| Validator, golden aggregate, overlap, large validate, NL validate, semantic bundle (Phase 3) | Unit tests — **pass** |
| Revenue API auth / org scope | `test_revenue_api.py` — **pass** |
| Analytics Stories 2.1–2.4 + auth | `test_analytics_api.py` — **pass** |
| Ingest E2E, loader, soft-delete, uniqueness, ingest auth | Integration tests — **pass** |
| NL query Stories 3.1–3.4 | `test_nl_query_api.py` — **pass** |
| HubSpot Phase 4 | `test_hubspot_phase4.py`, `test_hubspot_oauth_scopes.py` — **pass** |
| Health, `/auth/me`, batch 404 | `test_api_smoke.py` — **pass** |

---

## 4. Phase 5 acceptance criteria → tests

### Story 5.1 — Forecasting

| Acceptance criterion | Automated test | Status |
|----------------------|----------------|--------|
| Hybrid **imported** vs **statistical** with **source_mode** labeling | `test_story_5_1_forecast_series_filters_source_mode`; `test_story_5_1_statistical_refresh_requires_history` | `[x]` |
| **Forecast vs actual** not merged; explicit period boundary note | `test_story_5_1_forecast_vs_actual_explicit_separation` | `[x]` |
| **Versioning** — new import does not overwrite prior series id | `test_story_5_1_two_imports_create_distinct_series_ids` | `[x]` |
| **Statistical** methodology disclosure (model family, horizon) | `test_story_5_1_statistical_refresh_requires_history` | `[x]` |
| Prominent **UI disclaimer** (not audited financials) | **Manual** — `ForecastingPage.tsx` copy | `N/A` automated |
| **NUMERIC** money storage | Schema + CSV ingest path covered indirectly; amounts asserted as strings in APIs | `[x]` partial |

### Story 5.2 — Profitability modeling

| Acceptance criterion | Automated test | Status |
|----------------------|----------------|--------|
| **Cost facts** + **allocation rules** model (version, effective dates) | `test_story_5_2_cost_facts_traceable`; `test_story_5_2_allocation_rule_versioning` | `[x]` |
| Margin with **cost_scope** (COGS vs full) and **methodology_note** | `test_story_5_2_profitability_margin_and_cost_scope_note` | `[x]` |
| Traceability to **revenue and cost** lines (API lists) | Cost list by amount/source; profitability summary totals | `[x]` partial |

### Story 5.3 — Customer segmentation

| Acceptance criterion | Automated test | Status |
|----------------------|----------------|--------|
| **Stored rule** + **materialize** → **replayable** membership | `test_story_5_3_segment_materialize_replayable` | `[x]` |
| **Semantic** `forecast_total` / Phase 5 metrics in bundle | `test_semantic_bundle_includes_phase5_forecast_metric` | `[x]` |
| Org/BU scoping | Segment list filters by `owner_org_id` in API; materialize uses tenant + org rule | `[x]` partial |
| NL **disambiguation** for ambiguous segment terms | **Not** extended in new tests — Phase 3 behavior | `N/A` new |
| **Audit** who/when on definition changes | **Not** automated — DB columns exist; no dedicated audit event test | `[ ]` note |

### Story 5.4 — Multi-currency

| Acceptance criterion | Automated test | Status |
|----------------------|----------------|--------|
| **Single reporting currency** per tenant (default **USD** path) | `test_story_5_4_tenant_single_reporting_currency` | `[x]` |
| **FX rate** table: **effective date** + **rate_source** label | `test_story_5_4_fx_list_shows_rate_source_and_effective_date` | `[x]` |
| **No silent FX** — missing pair → **FX_RATE_MISSING** | `test_story_5_4_missing_fx_returns_fx_rate_missing` | `[x]` |
| **Consolidated** rollup: **reporting** + **native** + **FX metadata** | `test_story_5_4_consolidated_native_and_fx_metadata` | `[x]` |
| **Optional rate API** out of scope v1 | **N/A** per PRD | `N/A` |
| Phase 5 disabled → **503** on gated routes | `test_tenant_settings_503_when_phase5_disabled` | `[x]` |

---

## 5. Regression — Tech Lead touchpoints (Phase 5)

| Component | Verification |
|-----------|--------------|
| `app/main.py` — FX, forecast, profitability ingest, segments routers | Full suite — **pass** |
| `app/api/v1/analytics.py` — consolidated, profitability, forecast-vs-actual | Phase 5 integration + existing analytics tests — **pass** |
| `app/core/deps.py` — `require_phase5_enabled`, Phase 5 roles | Flag + RBAC tests — **pass** |
| `app/services/analytics/phase5_metrics.py` | Covered via consolidated / profitability / forecast-vs-actual endpoints — **pass** |
| `app/core/semantic_layer.yaml` | Unit test for `forecast_total` — **pass** |
| Phase 1–4 ingestion / revenue / NL / HubSpot | **pass** |

---

## 6. Known gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| Segment definition **audit trail** (who/when) not asserted | Medium (governance) | `updated_at` / `version` on definitions; dedicated audit API not required by AC text |
| **NL** queries mentioning forecast/segment without disambiguation | Low–Medium | Rely on Phase 3 patterns; add targeted NL tests if pilot demands |
| **`GET /costs/facts`** omits **`external_id`** | Low | Traceability via `cost_fact_id`; align list payload with Finance if needed |

---

## 7. Sign-off

| Role | Status |
|------|--------|
| **Quality Analyst (automation)** | **GO** for Phase 5 backend + semantic acceptance coverage; Phase 1–4 regression **pass**; run **`pip install -e ".[dev]"`** (or equivalent) so **pytest-asyncio ≥ 0.24** is used. |

---

*Aligned to [`product-requirements.md`](../requirements/product-requirements.md). UX alignment with `@ux-ui-designer`; schema with `@technical-architect`.*

**Revision history:**

| Date | Change |
|------|--------|
| 6 April 2026 | Initial Phase 5 QA report: 100 tests green; AC matrix; GO; pytest-asyncio tooling note. |
