# Phase 4 validation and QA sign-off

| Field | Value |
|--------|--------|
| **Document file** | `docs/qa/phase-4-report.md` (this file) |
| **Aligned to** | [`docs/requirements/phase-4-requirements.md`](../requirements/phase-4-requirements.md), [`.cursor/rules/quality-analyst.mdc`](../../.cursor/rules/quality-analyst.mdc) |
| **Last validated** | **6 April 2026** |
| **Legend** | `[x]` Done · `[ ]` Not done · `N/A` Out of scope per PRD |

---

## Executive recommendation

| Verdict | **GO** (Phase 4 HubSpot path) |
|---------|-------------------------------|
| **Rationale** | **Full suite:** **86 passed**, **0 skipped** (~19s). **Phase 1–3 regression** remains green (same cases as prior sign-off: analytics, ingest, NL query, revenue, smoke, loader, uniqueness, soft-delete). **Phase 4** adds **13** automated tests (11 integration + 2 unit) mapped to Stories **4.1–4.3**. **Frontend** `npm run build` **succeeds** (includes HubSpot integration page and routing). |
| **Residual risk** | **Live HubSpot OAuth and CRM APIs** are exercised in **pilot / manual** flows or with tenant credentials; CI uses **mocks** for sync and Celery. **TLS at rest / vault** for tokens align with deployment (Fernet bundle + `SECRET_KEY`); **TLS in transit** to HubSpot is **design-time** (HTTPS endpoints in code). |
| **Release debt** | Open questions in [`phase-4-requirements.md`](../requirements/phase-4-requirements.md) (connect roles beyond IT Admin, sync frequency defaults, sandbox for CI) remain **product** decisions, not blockers for this GO on implemented scope. |

---

## 1. Requirements source

- **Primary:** [`phase-4-requirements.md`](../requirements/phase-4-requirements.md) — Stories **4.1** (OAuth + health), **4.2** (incremental sync + audit), **4.3** (mapping, reconciliation, no silent overwrite of Excel).

---

## 2. Automation executed

```bash
cd backend && pytest tests/ -v --tb=short
```

**Result:** **86 passed**, **0 skipped**. Integration sessions **auto-migrate** to head per [`tests/conftest.py`](../../backend/tests/conftest.py) when integration tests are collected (unless `PYTEST_SKIP_ALEMBIC_UPGRADE` is set).

**New Phase 4 tests:**

- Unit: `tests/unit/test_hubspot_oauth_scopes.py`
- Integration: `tests/integration/test_hubspot_phase4.py`

**Frontend:**

```bash
cd frontend && npm run build
```

**Result:** **Success** (TypeScript + Vite production build).

---

## 3. Phase 1–3 regression (shared components)

| Area | Evidence |
|------|----------|
| Validator, golden aggregate, overlap, large validate, NL validate, semantic bundle | Unit tests — **pass** |
| Revenue API auth / org scope | `test_revenue_api.py` — **pass** |
| Analytics Stories 2.1–2.4 + auth | `test_analytics_api.py` (19 tests) — **pass** |
| Ingest E2E, loader, soft-delete, uniqueness, ingest auth | Integration tests — **pass** |
| NL query Stories 3.1–3.4 | `test_nl_query_api.py` — **pass** |
| Health, `/auth/me`, batch 404 | `test_api_smoke.py` — **pass** |

**Tech Lead / shared surface touched by Phase 4 (regression check):**

- **`app/main.py`** — HubSpot router mounted; no breakage to existing routes (full smoke + integration suite).
- **`app/core/deps.py`** — New HubSpot role gates; existing ingest/NL/audit deps unchanged in behavior (covered by role-specific tests).
- **`app/api/v1/analytics.py`** — New `GET /analytics/revenue/source-reconciliation`; existing analytics endpoints unchanged (**all `test_analytics_api` tests pass**).

---

## 4. Phase 4 acceptance criteria → tests

### Story 4.1 — OAuth connection to HubSpot

| Acceptance criterion | Automated test | Status |
|----------------------|----------------|--------|
| Secrets/tokens not hardcoded; OAuth uses **settings / env** | `test_story_4_1_build_authorization_url_uses_settings_client_id_not_hardcoded` | `[x]` |
| **Connection status** visible: connected / error / token refresh path | `test_story_4_1_status_surfaces_connected_error_and_token_refresh_failed`; disabled: `test_story_4_1_hubspot_disabled_returns_503` | `[x]` |
| **Least privilege** scopes for deals + companies (v1) | `test_story_4_1_default_scopes_are_least_privilege_deals_and_companies` | `[x]` |
| **Transport / storage** (TLS, encrypted bundle) | `N/A` in CI (HTTPS URLs and Fernet bundle in code; verify in deployment checklist) | `N/A` |

### Story 4.2 — Incremental sync

| Acceptance criterion | Automated test | Status |
|----------------------|----------------|--------|
| **Incremental** semantics (`last_modified_ms` / search vs full list + repair) | `test_story_4_2_incremental_sync_uses_search_after_cursor_not_full_list`; `test_story_4_2_repair_mode_does_not_use_incremental_search` | `[x]` |
| **Partial failure** not silent; row counts and error summary | `test_story_4_2_partial_failure_surfaces_completed_with_errors_and_counts` | `[x]` |
| **Async job** with UI-safe feedback (202, not blocking on worker) | `test_story_4_2_sync_returns_202_and_enqueues_task` (Celery `delay` mocked) | `[x]` |
| **Auditability** — sync runs visible (start/end, stats, correlation) | `test_story_4_2_sync_returns_202_and_enqueues_task` (lists `sync-runs`) | `[x]` |
| Retries on 429 / retriable failures | **Partial:** `HubspotApiClient` implements backoff; no live 429 in CI | `[ ]` note |

### Story 4.3 — External ID mapping and reconciliation

| Acceptance criterion | Automated test | Status |
|----------------------|----------------|--------|
| **Deals**-centric ingest + mapping table (`HubspotIdMapping`) | Covered by sync service + `mapping-exceptions` API (`test_story_4_3_mapping_exceptions_list_pending_unmapped`) | `[x]` |
| **Unmapped** entities as exceptions | `test_story_4_3_mapping_exceptions_list_pending_unmapped` | `[x]` |
| **Excel vs HubSpot** authority; **conflicts surfaced** | `test_story_4_3_detect_revenue_conflicts_surfaces_excel_vs_hubspot_mismatch`; `test_story_4_3_revenue_conflicts_api_lists_rows` | `[x]` |
| **Compare** aggregates where both exist | `test_story_4_3_reconciliation_report_compares_excel_and_hubspot_totals` | `[x]` |
| **Dedupe / grain** — same deal key upserts HubSpot facts | Existing `test_duplicate_external_id_same_source_fails` + `on_conflict` on `uq_fact_revenue_source_external` in sync | `[x]` |

---

## 5. Gaps and follow-ups (non-blocking)

- **End-to-end OAuth with real HubSpot** — Validate once per environment with pilot portal (per PRD open questions).
- **Celery worker + Redis** — Run a manual or staging smoke: enqueue sync and confirm worker processes `hubspot.run_sync` (mock proves API wiring only).
- **429 / retry** — Consider a dedicated unit test with mocked HTTP 429 if coverage is required for compliance narratives.

---

## 6. Sign-off

| Role | Status |
|------|--------|
| **Quality Analyst (this report)** | **GO** for Phase 4 implementation against [`phase-4-requirements.md`](../requirements/phase-4-requirements.md) |

---

*Aligned to [`product-requirements.md`](../requirements/product-requirements.md). UX alignment with `@ux-ui-designer`; schema with `@technical-architect`.*

**Revision history:**

| Date | Change |
|------|--------|
| 6 April 2026 | Initial Phase 4 QA report: 86 tests green, Phase 4 acceptance matrix, GO recommendation. |
