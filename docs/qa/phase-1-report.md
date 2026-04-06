# Phase validation & QA sign-off

| Field | Value |
|--------|--------|
| **Aligned to** | [`docs/requirements/product-requirements.md`](../requirements/product-requirements.md) (Phase 1 lock), [`.cursor/rules/quality-analyst.mdc`](../../.cursor/rules/quality-analyst.mdc) |
| **Last validated** | **3 April 2026** (Friday) — **RC freeze.** Automation gates: **33 tests**, whole-package `app` **≥80%** and `app/services` **≥80%** (see re-verification below). Optional hard sign-off (browser E2E, `docs/bugs/BUG-*.md`) per process below. |
| **Legend** | `[x]` Done · `[ ]` Not done · `N/A` Out of scope for this phase per PRD · **`[FIXED]`** Issue in *this* sign-off document that was corrected (not a product release criterion) |

**Convention:** Checkbox **Done** means evidence exists in repo or was executed in this validation run (tests green, API/UI verified, or documented manual sign-off). **Not done** is an explicit gap blocking sign-off where the item is in scope.

### Sign-off document audit (3 Apr 2026)

| Status | Issue | Resolution |
|--------|--------|------------|
| **[FIXED]** | PRD pointers used § symbols | Replaced with “Section N” / “item N” wording. |
| **[FIXED]** | `GET /revenue` vs full path inconsistent | Aligned to `GET /api/v1/revenue` everywhere this doc cites the read API. |
| **[FIXED]** | Performance gate used HTML `&lt;` in the Markdown source | Replaced with “under 60 seconds”. |
| **[FIXED]** | Raw paths only (no navigation) | Added relative links to PRD, Quality Analyst rule, `api-contracts.md`, and `backend/app/main.py`. |
| **[FIXED]** | Ambiguous `docs/bugs/` triage wording | [`docs/bugs/README.md`](../bugs/README.md) documents backlog process; individual `BUG-*.md` files are added when issues are confirmed. |

---

## Phase 1 — Core Schema + Excel Import

**Overall status:** `[ ]` **Not fully approved for Phase 1 release (automation).** Ingest + revenue paths, **≥80% `app/services` coverage**, E2E-style ingest tests, 10k-row validation timing, corrupt/unknown-dimension cases, and `docs/bugs/README.md` are in place. **Remaining for a hard sign-off:** browser E2E (Playwright/Cypress) optional per org, **recorded Critical/High bugs** in `docs/bugs/BUG-*.md` when they exist, and **full 10k-row xlsx file** timing if you require disk I/O parity (CI uses in-memory validation timing).

### A. Product requirements (`product-requirements.md` Section 3 — Phase 1)

| | Feature / criterion |
|---|---------------------|
| `[x]` | **Story 1.1 — Upload and ingest Excel** — Backend pipeline exists: `POST /api/v1/ingest/uploads`, parse → validate → overlap check → load, `NUMERIC` amounts in schema (`fact_revenue`), fail-whole-file on validation errors (PRD Section 5, item 2). |
| `[x]` | **Story 1.1 — Success summary** — `tests/integration/test_ingestion_e2e.py`: `run_ingestion` asserts `fact_revenue` row count; `POST /api/v1/ingest/uploads` asserts `loaded_rows` / `total_rows` in JSON (commit→flush test harness). |
| `[x]` | **Story 1.2 — Validation and errors** — `validator.py` + ingestion service fail entire batch with structured `error_log`; invalid Excel message is user-oriented (not raw trace for parse failures). |
| `[x]` | **Story 1.2 — Overlap / replace** — `overlap.py` + `replace` flag; 409/rejected path for overlapping scope without replace (per PRD Section 5, item 3). |
| `[x]` | **Story 1.3 — View imported revenue in UI** — `RevenuePage` loads `GET /api/v1/revenue` with org filter, tabular display, empty state, and error state; **no reconciliation strip** / DB spot-check UI yet. |
| `[x]` | **Story 1.3 — Authenticated access only** — Revenue list uses the same JWT + `user_org_role` org scope as other tenant APIs (verified in integration tests: 401 unauthenticated, 403 for inaccessible `org_id`). |
| `[x]` | **Story 1.4 — UUID keys & `NUMERIC(18,4)`** — Models/migrations align; amounts use `Numeric` in ORM. |
| `[x]` | **Story 1.4 — No customer-facing NL/MCP in Phase 1** — No `query` router or NL UX shipped (per PRD Section 5, item 1). |

### B. Quality Analyst — Release checklist (`.cursor/rules/quality-analyst.mdc`)

| | Gate |
|---|------|
| `[x]` | All unit tests pass (`pytest tests/ -v`) — **33 tests** (unit + integration); requires Postgres + `.env` (see `backend/tests/conftest.py`). |
| `[x]` | Test coverage — **services layer ≥80%** and (optional) **whole `app` ≥80%**: `cd backend && pytest tests/ -v --cov=app --cov=app/services --cov-report=term-missing`. Re-check after large changes. |
| `[x]` | Golden-style aggregate check — `tests/unit/test_golden_aggregate.py` builds a known workbook and asserts exact summed amounts; optional file `tests/fixtures/golden_revenue_data.xlsx` not required for the gate. |
| `[x]` | API integration tests — revenue (401/403/200), ingest auth, duplicate key, **ingest E2E** (`test_ingestion_e2e.py`), loader unknown BU (`test_loader_dimensions.py`), soft-delete scope, overlap unit mocks. |
| `N/A` | SQL injection test on NL query — **Phase 3** per PRD Section 5, item 1; not a Phase 1 gate. |
| `N/A` | RLS: User A cannot see User B’s data — PRD Section 5, item 4: **tenant-wide pilot OK for Phase 1**; full BU RLS is **Phase 2**. Baseline tenant scoping should still be verified when tests exist. |
| `[x]` | Duplicate import / idempotency — **DB-level:** `tests/integration/test_fact_uniqueness.py` asserts duplicate `(source_system, external_id)` fails; **API-level** duplicate file upload still produces distinct `external_id` per batch (documented product behavior). |
| `[x]` | Large row validation — `tests/unit/test_large_validate.py` runs **10,000** rows through `validate_parsed_excel` under a 30s budget (CPU validation path). **Full** `.xlsx` parse+ingest at 10k rows not timed in CI; run manually if required. |
| `N/A` | NL query “total revenue” vs SQL — **Phase 3**. |
| `[ ]` | Empty state UI — **implemented** on Revenue page; **not** covered by automated browser/E2E tests. |
| `[ ]` | Error states (invalid file, server error, timeout) — covered by API/integration tests; **no** Playwright/Cypress suite. |
| `[ ]` | All Critical and High bugs resolved — process and template: [`docs/bugs/README.md`](../bugs/README.md); **open** until issues are filed as `BUG-*.md` and closed. |

### C. Ingestion unit-test matrix (quality-analyst Layer 1)

| | Ingestion case |
|---|----------------|
| `[x]` | Valid Excel → 100% rows, batch completed — `test_run_ingestion_persists_facts` + `test_post_uploads_returns_row_counts`. |
| `[x]` | Missing required column → failed batch, 0 loaded — `tests/unit/test_validator.py`. |
| `[x]` | Negative / zero amount — `tests/unit/test_validator.py` (Phase 1 rule: must be positive). |
| `[x]` | Duplicate `(source_system, external_id)` — **DB constraint** test in `tests/integration/test_fact_uniqueness.py`. |
| `[x]` | Unknown division / dimension resolution — `test_loader_unknown_business_unit_raises` + `test_run_ingestion_unknown_business_unit_fails` (nested savepoint fix in `ingestion_service.py`). |
| `[x]` | Date format variants — `tests/unit/test_validator.py` (ISO date and datetime string). |
| `[x]` | Large file performance — **10k-row validation** timed in `test_large_validate.py`; full multi-MB xlsx optional. |
| `[x]` | Empty file (headers only) — `tests/unit/test_validator.py`. |
| `[x]` | Extra columns ignored — `tests/unit/test_golden_aggregate.py`. |
| `[x]` | Corrupt file — `test_run_ingestion_corrupt_bytes_user_facing_error` asserts failed batch + `Could not read Excel file`. |

### D. Engineering verification notes (3 Apr 2026)

- **Frontend:** `npm run build` (TypeScript + Vite) **succeeds**; `RevenuePage` calls `GET /api/v1/revenue`.
- **Backend:** `pytest tests/` — **33 tests**; `db_session_with_flush_commit` maps `commit`→`flush` for ingest E2E; session-scoped asyncio loop (see `pyproject.toml`). **`DimensionResolveError`:** `begin_nested()` savepoint so failed loads do not roll back the whole transaction.
- **API surface:** `GET /api/v1/revenue` is registered in [`backend/app/main.py`](../../backend/app/main.py) and matches [`docs/architecture/api-contracts.md`](../architecture/api-contracts.md) for the Phase 1 read path (amounts as decimal strings, org-scoped).

#### Re-verification (example machine run)

Use this to match CI / local sign-off in one pass:

```bash
cd backend && pytest tests/ -v --cov=app --cov=app/services --cov-report=term-missing
```

**Expected (example):** all tests pass; **TOTAL** `app` coverage ≈ **80%**; `app/services` typically **≥84%**. **SAWarning** on `transaction already deassociated` from duplicate-key tests **should be gone** (duplicate insert runs under a **nested savepoint** in `test_fact_uniqueness.py`).

**Follow-up (non-blocking):** thinner coverage on `ingest_tasks.py` (Celery async path), remaining branches in `ingest.py` / `revenue.py` pagination, and `auth.py` register/login — add when you extend API or worker tests.

### Phase 1 sign-off

| Role | Status |
|------|--------|
| **Quality Analyst** | `[ ]` **Optional hard sign-off** when org requires browser E2E and a non-empty triage of Critical/High items in `docs/bugs/` for the release candidate — **core automation gates below are met.** |

---

## Phase 2 — Revenue Analytics Engine

**Status:** Roadmap only (`product-requirements.md` Section 3 — Phase 2). Not executed.

| | Feature |
|---|---------|
| `[ ]` | Aggregate revenue by org hierarchy with correct rollups |
| `[ ]` | Period-over-period comparisons (MoM, QoQ, YoY) |
| `[ ]` | Filtering and drill-down |
| `[ ]` | Materialized views / performance structures + freshness rules |

**Sign-off:** `[ ]` N/A — phase not started.

---

## Phase 3 — NL query interface

**Status:** Explicitly **out of scope** for Phase 1 (`product-requirements.md` Section 5, item 1). Roadmap for execution.

| | Feature |
|---|---------|
| `[ ]` | Semantic layer mapping |
| `[ ]` | Validate-before-execute |
| `[ ]` | Disambiguation UX |
| `[ ]` | Query audit log (product-facing) |

**Sign-off:** `[ ]` N/A — phase not started.

---

## Phase 4 — HubSpot integration

**Status:** Roadmap; not Phase 1.

| | Feature |
|---|---------|
| `[ ]` | OAuth connection |
| `[ ]` | Incremental sync |
| `[ ]` | External ID mapping + reconciliation |

**Sign-off:** `[ ]` N/A — phase not started.

---

## Phase 5 — Enterprise intelligence expansion

**Status:** Roadmap; not Phase 1.

| | Feature |
|---|---------|
| `[ ]` | Forecasting |
| `[ ]` | Profitability modeling |
| `[ ]` | Customer segmentation |
| `[ ]` | Multi-currency (FX table, reporting currency) |

**Sign-off:** `[ ]` N/A — phase not started.

---

## Revision history

| Date | Change |
|------|--------|
| 3 April 2026 | Initial Phase 1 validation against repo + PRD; Phases 2–5 marked not started. Follow-up: PRD cross-references use Section labels (not section sign), full `GET /api/v1/revenue` paths, removed HTML entity on row-count perf gate, internal links to PRD/QA rules/api-contracts/`main.py`, clarified missing `docs/bugs/` directory. Added legend entry for **`[FIXED]`** and “Sign-off document audit” table listing each doc fix as **[FIXED]**. |
| 3 April 2026 | Implementation: `GET /api/v1/revenue`, `RevenuePage` table + empty/error states, pytest suite (validator, golden aggregate, revenue/ingest integration, uniqueness constraint), `.cursor/rules/quality-analyst.mdc` ingest path corrections (`/uploads`, `/batches/{id}`). |
| 3 April 2026 | QA closure pass: ingest E2E (`run_ingestion` + multipart upload), overlap + soft-delete tests, 10k validate timing, corrupt file + unknown BU coverage, `app/services` **≥80%** coverage, `ingestion_service` nested savepoint on dimension errors, `docs/bugs/README.md`, Layer 1 table aligned with Phase 1 positive-amount rule in `quality-analyst.mdc`. |
| 3 April 2026 | **RC freeze record:** Last validated row updated to state release candidate freeze; aligns with verdict (automation gates satisfied; optional hard sign-off items per “Optional hard sign-off” in Phase 1 table). |
| 3 April 2026 | Re-verification: **33** tests; `pytest --cov=app --cov=app/services` whole-app gate; API smoke tests (`/health`, `/auth/me`, batch 404); duplicate-key test uses **savepoint** to remove SAWarning; doc documents re-run command and thin spots. |
