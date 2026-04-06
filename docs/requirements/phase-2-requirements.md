# Phase 2 Requirements — Revenue Analytics Engine

| Field | Value |
|--------|--------|
| **Document status** | **APPROVED** |
| **Approval date** | **3 April 2026** |
| **Approved by** | Product Owner |
| **Parent document** | [`product-requirements.md`](product-requirements.md) (Section 3 — Phase 2; Section 4 — NFRs; Section 5 — approved decisions) |
| **Phase 2 lock** | **LOCKED** — Requirements in this document are frozen for Phase 2 execution as of the approval date. Implementation, QA, and design SHALL align with this baseline. Scope, acceptance criteria, or material changes require a **written change request** and **Product Owner re-approval** (updated status block and revision note). |
| **Depends on** | Phase 1 complete and QA sign-off per [`docs/qa/phase-1-report.md`](../qa/phase-1-report.md) |

---

## Phase goal (one sentence)

**Leaders and finance users can analyze revenue by org hierarchy and time—with period-over-period comparisons, filtering, and drill-down—without exporting to Excel for pivoting, with interactive performance backed by documented precomputed structures.**

---

## What Phase 1 delivered that Phase 2 builds on

Phase 1 established the **canonical revenue model**, **governed Excel ingestion** (fail-whole-file validation, structured errors, overlap/replace batches), **immutable import batches**, **`NUMERIC`-grade amounts**, **tenant-scoped APIs** (`POST /api/v1/ingest/uploads`, `GET /api/v1/revenue`), and a **simple UI** to upload, validate, and view tabular revenue. That **persisted fact data and hierarchy dimensions** are the foundation for aggregations, comparisons, and drill-down in Phase 2. Per approved product decisions, Phase 1 intentionally did **not** ship hierarchy rollups, materialized analytics, natural language, or HubSpot—those remain sequenced per phase.

---

## User stories — Phase 2 only

Stories are numbered **2.1–2.4** to align with [`product-requirements.md`](product-requirements.md). Format: **Given / When / Then**.

### Story 2.1 — Aggregate revenue by org hierarchy

**Given** revenue facts exist for multiple business units and divisions under an organization, **when** I choose a hierarchy level (for example org, BU, or division) and a time scope supported by the product, **then** I see totals that roll up correctly at each level for that scope.

**Acceptance criteria**

- Child totals sum to parent totals for the same period(s) and filter set (reconciliation holds at each rollup level).
- Changing hierarchy scope (for example from org to BU) updates results deterministically for the same underlying facts.
- Displayed amounts match database-derived aggregates for the same filters (spot-check path for Finance, consistent with NFRs in Section 4 of the parent PRD).
- **Row-level access:** Users see only hierarchy nodes and facts they are allowed to see per the **Phase 2** access model (approved decision: row-level BU scoping is required when hierarchy analytics ship—see “Architect input” below).

---

### Story 2.2 — Period-over-period comparisons

**Given** I select a metric (for example revenue) and a comparison (for example month-over-month, quarter-over-quarter, or year-over-year, as supported in this phase), **when** I run the comparison for explicit periods, **then** I see both absolute and relative change with **clear labeling of which periods** are being compared.

**Acceptance criteria**

- Period boundaries are explicit in the UI (no ambiguous “last quarter” without confirmation—explicit date and/or period pickers or clearly labeled presets).
- If data is missing for one leg of the comparison, the UI states what is missing rather than implying zero revenue.
- Comparison logic uses the same canonical definitions as aggregates in Story 2.1 (single definition of truth for “revenue” in analytics—per parent PRD Section 4).

---

### Story 2.3 — Filtering and drill-down

**Given** I am viewing a summary (for example rolled-up revenue), **when** I apply filters (for example BU, division, revenue type, customer—within Phase 2 scope) or drill from summary to detail, **then** the detail view applies the same filters and **reconciles** to the rolled-up total from the same underlying facts as Phase 1 ingestion.

**Acceptance criteria**

- Drill-down from summary to detail ties to `fact_revenue` (and related dimensions) without silent drops or double-counting.
- Filters combine predictably (documented behavior for “AND” across dimensions unless product specifies otherwise).
- Performance meets interactive expectations from the parent PRD Section 4 (sub–few seconds for typical queries where stated; heavy queries may defer to async with user-visible progress if engineering selects that pattern—confirm with architect).

---

### Story 2.4 — Performance via precomputed structures

**Given** fact tables grow to enterprise sizes, **when** users run common hierarchical and time-series queries, **then** responses remain within performance expectations through **materialized views or equivalent** precomputation, with **documented refresh and freshness** behavior.

**Acceptance criteria**

- Refresh strategy is documented: when precomputed structures refresh after new loads, and how users know if data is stale.
- No incorrect results due to stale caches: either freshness guarantees **or** explicit “as of” timestamps / stale indicators (per parent PRD Phase 2 story 2.4).
- Operational clarity for IT: how refresh interacts with ingest batches and failures (align with observability expectations in personas).

---

## Explicitly out of scope for Phase 2

Per [`product-requirements.md`](product-requirements.md) Phase 2:

- **Natural language** query interface, semantic layer, and MCP-driven CXO query UX (**Phase 3**).
- **HubSpot** and other external CRM ingestion beyond Excel (**Phase 4+**).
- **Forecasting, profitability modeling, customer segmentation, multi-currency** (**Phase 5**).
- Replacing **Finance-owned general ledger**; the platform remains a **revenue intelligence** layer unless direction changes.
- **Full enterprise SSO** as the default Phase 2 gate: approved decision is **application auth** for MVP with **SSO planned later** unless a pilot contract mandates otherwise—Phase 2 still must deliver **row-level BU scoping** for hierarchy analytics, not necessarily full IdP integration in this phase.

---

## Decisions that need architect input before we proceed

These items should be resolved in design review ( **`@technical-architect`** per parent PRD Section 5 and schema governance) before locking Phase 2 implementation:

1. **Precomputation strategy** — Materialized views vs. other rollups (summary tables, incremental aggregates): naming, indexing, and **refresh triggers** (on batch commit, scheduled, or hybrid) to meet NFRs without violating accuracy rules.
2. **Row-level BU scoping** — How authorization maps to org hierarchy keys in the schema and APIs (including `GET` analytics endpoints and any new read models); migration path from Phase 1 **tenant-wide pilot** to Phase 2 **BU-scoped** access.
3. **Analytics API surface** — Whether to extend `GET /api/v1/revenue` or introduce versioned analytics routes (for example under `/api/v1/analytics/...`); pagination and sorting contracts for drill-down.
4. **Comparison calendar** — Fiscal vs. calendar periods: data model and API support if pilot customers use non-calendar fiscal quarters (may affect period-boundary logic for Story 2.2).
5. **Stale-read semantics** — Exact UX contract for Story 2.4: blocking until refresh completes vs. serving last-known aggregates with visible “as of” time (must not misstate financial results).

---

## Follow-up decisions (non-blocking)

These items refine implementation detail and may be resolved during Phase 2 design or pilot onboarding. They **do not** override the approved scope and acceptance criteria above unless captured in a change request.

1. **Comparison types in Phase 2 v1:** Whether **MoM, QoQ, and YoY** all ship in the first Phase 2 release, or a smaller set (for example YoY + MoM only) for an earlier cut.
2. **Minimum drill-down depth:** **Customer-level** vs **division-level** (plus revenue type) for the first release.
3. **Pilot tenants:** Any committed customer requiring **fiscal period** reporting in Phase 2 (not only calendar month/quarter/year).
4. **Replace vs. analytics:** After a **replace** import (approved Phase 1 behavior), whether analytics must reflect new facts **immediately** or a short **documented** consistency window is acceptable.
5. **Currency:** Phase 5 covers multi-currency; Phase 2 remains **single reporting currency** per tenant (for example USD) unless a change request updates this document.

---

*Aligned to [`product-requirements.md`](product-requirements.md). UX alignment with `@ux-ui-designer`; quality gates with `@quality-analyst`.*

**Revision history:** 3 April 2026 — Document **APPROVED**; Phase 2 requirements locked; status block and follow-up section finalized.
