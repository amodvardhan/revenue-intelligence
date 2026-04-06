# Phase 3 validation and QA sign-off

| Field | Value |
|--------|--------|
| **Document file** | `docs/qa/phase-3-report.md` (this file) |
| **Aligned to** | [`docs/requirements/phase-3-requirements.md`](../requirements/phase-3-requirements.md), [`.cursor/rules/quality-analyst.mdc`](../../.cursor/rules/quality-analyst.mdc) |
| **Last validated** | **6 April 2026** (re-verified same day) |
| **Legend** | `[x]` Done · `[ ]` Not done · `N/A` Out of scope per PRD |

---

## Executive recommendation

| Verdict | **GO** (Phase 3 NL path) |
|---------|----------------------------|
| **Rationale** | **Full suite:** **73 passed**, **0 skipped** (latest run ~13s). **Phase 1–2 regression** remains green. **Phase 3** integration tests for Stories **3.1–3.4** execute **without skip** against the same Postgres as pytest: **`tests/conftest.py`** runs **`alembic upgrade head`** in **`pytest_collection_finish`** whenever the collected session includes **`tests/integration`** (opt-out: **`PYTEST_SKIP_ALEMBIC_UPGRADE=1`**). NL mocks patch **`app.services.query_engine.service.complete_nl_plan`** so the orchestrator’s bound import is replaced (patching **`llm.complete_nl_plan`** alone does not). **`semantic_layer_version`** and related Phase 3 objects are present after upgrade. **Frontend** `npm run build` **succeeds** (re-verified). |
| **Remediation (historical)** | Prior **NO-GO** was due to migration **20260406_0003** not applied on the validation DB; this is addressed by **automatic Alembic upgrade** before integration runs. Manual **`cd backend && alembic upgrade head`** remains valid for deployments. |
| **Release debt** | **365-day retention** for audit rows is a **PRD decision** not enforced by automated TTL here. **Append-only** audit semantics are **by design** (insert-only API surface). |

---

## 1. Requirements source

- **Primary:** [`phase-3-requirements.md`](../requirements/phase-3-requirements.md) — Stories **3.1** (semantic layer + consistency with Phase 2), **3.2** (validate before execute), **3.3** (disambiguation), **3.4** (query audit log).
- **Architecture delta:** [`phase-3-changes.md`](../architecture/phase-3-changes.md).

---

## 2. Automation executed

```bash
cd backend && pytest tests/ -v --cov=app --cov=app/services --cov-report=term-missing
```

**Result:** **73 passed**, **0 skipped**. Integration sessions **auto-migrate** to head unless **`PYTEST_SKIP_ALEMBIC_UPGRADE`** is set.

**Focused NL file:**

```bash
cd backend && pytest tests/integration/test_nl_query_api.py -v
```

**Frontend:**

```bash
cd frontend && npm run build
```

**Result:** **Success** (TypeScript + Vite production build).

---

## 3. Phase 1–2 regression (unchanged baseline)

| Area | Evidence |
|------|----------|
| Validator, golden aggregate, overlap, large validate | Unit tests — **pass** |
| Revenue API auth / org scope | `test_revenue_api.py` — **pass** |
| Analytics Stories 2.1–2.4 | `test_analytics_api.py` — **pass** |
| Ingest E2E, loader, soft-delete, uniqueness, ingest auth | Integration tests — **pass** |
| Health, `/auth/me`, batch 404 | `test_api_smoke.py` — **pass** |

---

## 4. Phase 3 acceptance criteria → tests

### Story 3.1 — Map business terms to the semantic layer

| Acceptance criterion | Automated test | Status |
|----------------------|------------------|--------|
| Maintainable semantic artifact + traceability (`semantic_layer.yaml`, version / hash) | `test_semantic_bundle_has_version_label_and_stable_hash` | `[x]` |
| Model identifier from settings / env (not hardcoded in LLM call path) | `test_complete_nl_plan_uses_openai_model_from_settings` | `[x]` |
| Interpretation consistent with Phase 2 analytics for same filters | `test_story_3_1_nl_rollup_matches_analytics_api` | `[x]` |
| Governance read of active version + hash after NL sync | `test_story_3_4_audit_detail_includes_resolved_plan_after_success` | `[x]` |

### Story 3.2 — Validate before execute

| Acceptance criterion | Automated test | Status |
|----------------------|------------------|--------|
| Reject unsupported / unsafe structured intents | `test_validate_plan_rejects_unsupported_intent`; `test_story_3_2_invalid_plan_returns_400_not_stack_trace` | `[x]` |
| Enforce date-span envelope (least privilege / safety envelope) | `test_validate_plan_rejects_date_range_exceeding_envelope` | `[x]` |
| Execution via Phase 2 analytics services (no raw LLM SQL) | `test_story_3_1_nl_rollup_matches_analytics_api` | `[x]` |

### Story 3.3 — Disambiguation

| Acceptance criterion | Automated test | Status |
|----------------------|------------------|--------|
| User-visible clarification path (ambiguous quarter → token + follow-up) | `test_story_3_3_disambiguation_round_trip` | `[x]` |
| No silent completion when clarification required | Asserted in same test (`needs_clarification` then second POST with token; LLM called once) | `[x]` |
| Audit captures interpretation (incl. resolved plan on success) | `test_story_3_4_audit_detail_includes_resolved_plan_after_success` | `[x]` |

### Story 3.4 — Query audit log

| Acceptance criterion | Automated test | Status |
|----------------------|------------------|--------|
| Append-only primary store (no casual edits via API) | **N/A** automated — design review; no update/delete routes on audit | `N/A` |
| **365-day retention** in primary store | **N/A** in test suite — not asserted (operational / job) | `N/A` |
| Authenticated, role-appropriate access | `test_story_3_4_query_audit_requires_authentication` (401); `test_story_3_4_viewer_cannot_list_audit` (403) | `[x]` |
| Detail includes resolved plan + correlation | `test_story_3_4_audit_detail_includes_resolved_plan_after_success` | `[x]` |

---

## 5. Regression — Tech Lead touchpoints (Phase 3)

| Component | Verification |
|-----------|--------------|
| `app/main.py` — query + semantic-layer routers | Full suite — **pass** |
| `app/api/v1/query.py`, `app/api/v1/semantic_layer.py` | NL + audit + RBAC — **pass** |
| `app/services/query_engine/*`, `app/core/semantic_layer.py` | Unit + integration — **pass** |
| `app/services/analytics/service.py` (reuse from NL) | Cross-check in `test_story_3_1_nl_rollup_matches_analytics_api` — **pass** |
| Phase 2 ingestion / revenue / analytics | **pass** |

---

## 6. Known gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| Audit retention **365 days** not verified in automation | Medium (process) | Align with ops / compliance; optional scheduled purge or archive tests later |
| OpenAI default `gpt-4o-mini` in `Settings` | Low | Env may override; LLM request path uses `settings.OPENAI_MODEL` (see unit test) |
| `session.commit()` on NL route may emit **SAWarning** in tests | Low | Harmless; transactional test harness |

---

## 7. Sign-off

| Role | Status |
|------|--------|
| **Quality Analyst (automation)** | **GO** for Phase 3 — Section 4 AC rows **exercised** with **0 skips**; Phase 1–2 regression **pass**. |

---

## Revision history

| Date | Change |
|------|--------|
| 6 April 2026 | Initial Phase 3 QA report: 68 passed / 5 skipped; AC matrix; Tech Lead regression; NO-GO pending Phase 3 migration. |
| 6 April 2026 | **GO:** Auto `alembic upgrade head` in `tests/conftest.py` for integration sessions; NL integration mocks patch `service.complete_nl_plan`; **73 passed / 0 skipped**. |
| 6 April 2026 | **Re-verify:** Full `pytest tests/ -v` — **73 passed**, **0 skipped**; `npm run build` — **OK**; one **SAWarning** on `test_story_3_2_invalid_plan_returns_400_not_stack_trace` (transaction rollback harness; see §6). |
