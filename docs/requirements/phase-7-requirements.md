# Phase 7 Requirements — Customer Revenue Operations & Standardized Workbook I/O

| Field | Value |
|--------|--------|
| **Document status** | **APPROVED** |
| **Approval date** | **8 April 2026** |
| **Approved by** | Product Owner |
| **Parent document** | [`product-requirements.md`](product-requirements.md) — **Phases 1–6 are unchanged and remain locked** per their respective approval dates. Phase 7 **adds** capabilities **on top of** Phases 1–6. |
| **Phase 7 lock** | **LOCKED** for Phase 7 execution — scope, acceptance criteria, or material changes require a **written change request** and **Product Owner re-approval**. |
| **Depends on** | Phases 1–6 complete (or parallel UI work gated behind feature flags per tech lead), with **Phase 6** supplying enterprise identity where email notifications must resolve named users securely. |

---

## Phase goal (one sentence)

**Operations and delivery leaders get customer-level revenue in an Excel-familiar matrix, hierarchical comparisons (organization → business unit → division → customer), automated discrepancy signals with accountable explanations, and **standardized** import/export aligned to an agreed workbook template—without altering the locked scope of Phases 1–6.**

---

## Relationship to Phases 1–6 (no regression)

| Phase | What stays true |
|-------|-----------------|
| **1–2** | Canonical schema, Excel ingestion, hierarchical analytics — Phase 7 **extends** templates and views; it does **not** replace Phase 1 validation rules unless a **separate** change request updates Phase 1. |
| **3** | NL / semantic layer — Phase 7 may **surface** the same measures in UI; no requirement to add new NL intents unless explicitly decided. |
| **4** | HubSpot — workbook may **reference** CRM-oriented sheets in exports; **conflict rules** in parent PRD §5 remain. |
| **5** | Forecasting, FX, segments — Phase 7 **respects** reporting currency and segment semantics where shown in grids. |
| **6** | SSO, audit export, admin — **Delivery manager** notifications use **verified** user identity and **audited** explanation events. |

---

## Reference workbook analysis — `samples/EUROPE_Weekly Commercial Dashboard.xlsx`

The following is a **factual summary** of the sample file (inspected **8 April 2026**) to drive **standardized** import/export mapping. Other sheets in the file are **supporting** operational tabs; **v1 standard** focuses on the primary customer-month matrix unless product expands.

### Sheet `Sheet1` (primary monthly customer matrix)

| Aspect | Observation |
|--------|----------------|
| **Layout** | Column **A** is unused in the header row; data starts column **B**. |
| **Fixed columns (row 2)** | `Sr. No.` · `Customer Name` · `Customer Name` (duplicate header label) |
| **Month columns** | **13** month-end columns as Excel **dates**: **Dec 2025** through **Dec 2026** (stored as first-of-month datetimes). Display labels in UI/export should follow **`Mon-YY`** (e.g. `Dec-25`, `Jan-26`) to match business convention. |
| **Dual customer columns** | Sample data uses the **first** `Customer Name` for **legal / full** name and the **second** for **common / short** name (e.g. `Creiss Systems GmbH` / `Creiss`). Product standard: **`customer_name_legal`** and **`customer_name_common`**. |
| **Row pairing** | For each customer, **two** rows: (1) **absolute** monthly revenue, (2) **period delta** (e.g. month-over-month change), with the first columns blank on the delta row. Ingestion **must** classify row type (e.g. `value` vs `delta`) or **derive** deltas in-app and **skip** duplicate delta rows on import per architect rules. |

### Other sheets (non-primary for v1 standard; may inform Phase 7.2+)

| Sheet | Role (summary) |
|-------|----------------|
| `EN,NN,New Logo-CW` | Deal-level rows: Company, Deal Name, dealid, monthly CY amounts, **BU**, Territory, LOB, etc. |
| `Unfulfilled Allocation - CW` | Project / **Whizible ID**, customer, monthly splits, **DU Manager**, SBU, geography. |
| `Goal` | **BU**, Customer Name, GOAL, **DU**, Geo. |
| `Actual Changes-*` | Week-over-week style comparisons with **Comments** columns. |

**Architect handoff:** Full mapping, row-type detection, and optional multi-sheet ingest are specified in [`docs/architecture/phase-7-changes.md`](../architecture/phase-7-changes.md). **Implementation handoff** (technical lead, UX/UI, QA): [`docs/architecture/phase-7-implementation-handoff.md`](../architecture/phase-7-implementation-handoff.md).

---

## User stories — Phase 7 only

Stories are numbered **7.1–7.5**. Format: **Given / When / Then**.

### Story 7.1 — Customer-wise revenue as a first-class view

**Given** revenue facts are tied to **customers** and hierarchy (org → BU → division), **when** a delivery or finance user opens the **customer revenue** experience, **then** they see **totals and periods** at **customer** grain with clear linkage to **division** and **BU** under **organization**.

**Acceptance criteria**

- **GIVEN** imported data, **WHEN** filtering by org/BU/division, **THEN** customer rows shown **match** rolled-up facts (same reconciliation standard as Phase 2).
- **GIVEN** a customer with multiple divisions (if allowed by data model), **WHEN** viewing detail, **THEN** the UI does not **double-count** without an explicit rule (architect-defined).

---

### Story 7.2 — Compare revenue: customer × division within BU under organization

**Given** hierarchical scope, **when** a user runs a **comparison** (e.g. month vs prior month, or vs same month prior year—**exact comparison types** fixed in design), **then** they can compare **per customer** and **per division** within the selected **BU** and **organization**, with consistent drill paths.

**Acceptance criteria**

- **GIVEN** a selected path `organization → BU → division`, **WHEN** comparing periods, **THEN** **child scopes** reconcile to **parent** totals for the same filters.
- **GIVEN** insufficient data for a comparison leg, **WHEN** rendering, **THEN** the UI states **missing** data explicitly (aligned with Phase 2 NFRs).

---

### Story 7.3 — Discrepancy detection, email to delivery manager, and explanation capture

**Given** configurable **discrepancy rules** (threshold, period, scope—**defaults** in design), **when** a rule fires (e.g. material variance vs prior period or vs plan), **then** the **delivery manager** receives an **email** with a **secure link** to a **variance explanation** page.

**Acceptance criteria**

- **GIVEN** a triggered discrepancy, **WHEN** the delivery manager opens the link, **THEN** they can record a **reason** for **up** or **down** movement (free text with optional categories—**fixed in design**).
- **GIVEN** a saved explanation, **WHEN** auditors or finance review, **THEN** **who / when / scope** is visible (append-only or audited updates per architect).
- **GIVEN** Phase 6 SSO, **WHEN** sending mail, **THEN** recipient identity follows **tenant** directory rules (no silent send to unverified addresses).

**Out of scope (v1 unless pulled forward)**

- Full **workflow engine** with multi-step approvals.
- **SMS** or chat integrations.

---

### Story 7.4 — Excel-like grid for delivery directors (green / red at a glance)

**Given** comparison results, **when** a **delivery director** opens the **matrix view**, **then** cells use **green** for **growth** and **red** for **decline** (and neutral styling for flat/missing—**exact tokens** per `@ux-ui-designer`), matching spreadsheet mental models without breaking accessibility (not **color-only** meaning).

**Acceptance criteria**

- **GIVEN** WCAG-oriented constraints, **WHEN** viewing the grid, **THEN** direction of change is available via **text or icon** in addition to color.
- **GIVEN** export to Excel, **WHEN** downloading, **THEN** formatting follows **standardized** template rules (Story 7.5).

---

### Story 7.5 — Standardized import and export (canonical workbook)

**Given** the **approved** column layout (Sr. No., dual customer names, 13 monthly columns **Dec-25 … Dec-26** pattern for a rolling or fixed window—**versioned**), **when** users **import** or **export**, **then** the platform validates **headers and types**, maps **legal/common** customer names, and produces **consistent** files for Finance and operations.

**Acceptance criteria**

- **GIVEN** a conforming file, **WHEN** importing, **THEN** validation errors are **row/column actionable** (aligned with Phase 1 spirit; Phase 1 **fail-whole-file** rule remains unless Phase 7 explicitly documents a **template-specific** exception—**architect decision**).
- **GIVEN** export, **WHEN** downloaded, **THEN** layout matches **published** template version (document ID in `docs/architecture/` or design spec).
- **GIVEN** the reference file [`samples/EUROPE_Weekly Commercial Dashboard.xlsx`](../../samples/EUROPE_Weekly%20Commercial%20Dashboard.xlsx), **WHEN** defining mappings, **THEN** `Sheet1` is the **primary** interop surface for **v1**; other sheets are **out of scope** for mandatory import unless listed in `phase-7-changes.md`.

---

## Approved product decisions (Phase 7)

| # | Topic | Decision |
|---|--------|----------|
| 1 | **Canonical monthly matrix** | **13 months** starting **Dec of year N** through **Dec of year N+1**, with **two** customer name columns (**legal**, **common**), plus **Sr. No.** — aligned to provided reference image and `Sheet1` sample. |
| 2 | **Delta rows in Excel** | **Either** ingest as explicit **row_type** **or** ignore duplicate “delta” rows and compute in application — **architect** picks one for idempotency and reconciliation. |
| 3 | **Discrepancy rules** | **Configurable** per tenant: thresholds and comparison baseline (e.g. MoM, vs goal when goals exist); **default** values require PO + architect sign-off. |
| 4 | **“Delivery manager”** | Mapped to **user** or **role** in tenant directory; **email** uses Phase 6–compliant identity. |
| 5 | **Phases 1–6** | **No** retroactive change to locked phase docs; Phase 7 is **additive**. |

---

## Out of scope (Phase 7)

- Replacing **general ledger** or **official** revenue recognition systems.
- **Real-time** collaboration inside the spreadsheet file (Google Sheets–style).
- **Automatic** correction of source Excel formulas (`#REF!`, etc.) in non-primary sheets — imports **reject** or **skip** per architect rules.

---

## Decisions that need architect input

Captured in [`docs/architecture/phase-7-changes.md`](../architecture/phase-7-changes.md): `dim_customer` extensions, variance/explanation tables, notification pipeline, import row classification, API surface, and indexes.

---

*Technical schema and migrations: **`@technical-architect`** — [`phase-7-changes.md`](../architecture/phase-7-changes.md). UX: **`@ux-ui-designer`** — grid density, green/red semantics with accessible non-color cues.*

**Revision history:**

| Date | Change |
|------|--------|
| 8 April 2026 | Initial **APPROVED** Phase 7 scope; reference workbook analysis; additive to Phases 1–6. Pointer to [`phase-7-implementation-handoff.md`](../architecture/phase-7-implementation-handoff.md) added for TL/UX/QA. |
