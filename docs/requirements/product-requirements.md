# Product Requirements — Enterprise Revenue Intelligence Platform

| Field | Value |
|--------|--------|
| **Document status** | **APPROVED** |
| **Approval date** | **3 April 2026** |
| **Approved by** | Product Owner |
| **Phase 1 lock** | **LOCKED** — Product requirements for **Phase 1 (Core Schema + Excel Import)** are frozen as of the approval date. Implementation, QA, and design SHALL align with Phase 1 as stated in this document. Any change to Phase 1 scope, acceptance criteria, or the approved decisions in §5 requires a **written change request** and **Product Owner re-approval** (updated status block and revision note). **Phases 2–6** are described in Section 3 and remain **unchanged**; **Phase 6** authoritative requirements and **Approved product decisions** are in [`phase-6-requirements.md`](phase-6-requirements.md) (approved **6 April 2026**). **Phase 7** is **additive only**; authoritative requirements are in [`phase-7-requirements.md`](phase-7-requirements.md) (approved **8 April 2026**). |

**Document type:** Product requirements (vision, personas, phased deliverables, NFRs, approved decisions)  
**Source context:** `.cursorrules/cursor.md`, Product Owner phase contract  
**Stack reference:** FastAPI, PostgreSQL, React, Celery, Redis, Python MCP SDK, OpenAI API (model from configuration)

---

## 1. Product Vision

Enterprises need a single, trustworthy view of revenue that leaders can explore without waiting on analysts or learning SQL. The Enterprise Revenue Intelligence Platform solves this by combining a canonical revenue data model, controlled ingestion from spreadsheets and (later) CRM systems, and natural-language analytics so CXOs and business owners get answers in the language they already use. The product is built for organizations where revenue reporting must be auditable, hierarchical, and safe to use in financial and board-level conversations.

---

## 2. User Personas

### CXO / C-Suite

| Need | Pain we address |
|------|-----------------|
| Fast answers to revenue questions (totals, trends, comparisons) without a ticket to BI or Finance | Dependency on analysts and slow reporting cycles |
| Confidence that numbers are consistent and traceable for board and investor narratives | Fragmented spreadsheets and conflicting definitions |
| Ability to explore hierarchically (org → business unit → division) as they think about the business | Static dashboards that do not match mental models |

**What they need from the product:** Executive-grade clarity, minimal training, and defensible figures. Natural language query (when available) reduces friction; until then, curated views and analytics must still feel “CXO-ready.”

### BU Head

| Need | Pain we address |
|------|-----------------|
| Drill-down into their unit’s revenue, periods, and segments | Waiting for consolidated reports that obscure their slice |
| Filters and comparisons relevant to their P&amp;L scope (e.g., MoM, YoY for their BU) | Generic org-wide reports that hide operational detail |
| Clear lineage from a metric back to source data | Distrust when numbers do not reconcile to what they submitted |

**What they need from the product:** Scoped visibility to their hierarchy, responsive analytics, and transparency into how totals roll up.

### Finance Team

| Need | Pain we address |
|------|-----------------|
| Numeric precision, auditability, and reconciliation to source files or systems | Rounding errors, float-based money, and “black box” analytics |
| Traceability from reported metrics to ingested rows and import batches | Manual reconciliation and spreadsheet chaos |
| Controls aligned with financial governance (who loaded what, when) | Informal data sharing with no audit trail |

**What they need from the product:** `NUMERIC`-grade amounts, validation on ingest, import history, and exports or views that support reconciliation—not marketing approximations.

### IT Admin

| Need | Pain we address |
|------|-----------------|
| Authentication, authorization, and segregation of duties by org/BU where required | Uncontrolled access to sensitive financial data |
| Audit logs for data loads and (later) high-risk actions such as NL queries | Compliance gaps and inability to demonstrate controls |
| Manageable integrations (e.g., HubSpot OAuth, sync health) without custom scripting | One-off integrations and operational firefighting |
| Operational clarity: environments, secrets, monitoring | Hardcoded keys and opaque failures |

**What they need from the product:** Secure configuration, observable pipelines, integration management, and auditability suitable for enterprise IT policies.

---

## 3. Phase Deliverables

Each phase must be complete before the next begins. Phases follow `.cursorrules`: **CURRENT_PHASE=1** until explicitly advanced.

---

### Phase 1: Core Schema + Excel Import

**Phase goal:** Establish the canonical revenue model and a reliable Excel ingestion path so structured revenue data exists in the platform and can be validated and reviewed in a simple UI.

**Business value delivered:** The organization can load revenue data from Excel into a governed schema, see validation outcomes, and inspect imported data—creating a trusted foundation before analytics and natural language.

#### User stories (Given / When / Then)

**Story 1.1 — Upload and ingest Excel revenue data**

- **Given** I have an Excel file that maps to the expected revenue layout, **when** I upload it through the application, **then** the system ingests rows into the core schema and confirms success with a summary (e.g., rows processed, period covered).
- **Acceptance criteria**
  - Successful uploads persist facts with correct linkage to org hierarchy entities as defined in schema (e.g., org, BU, division, customer, revenue type).
  - Failed rows are reported with actionable messages; partial success behavior is defined and consistent (documented outcome: reject file vs. skip bad rows—see Open Questions).
  - All monetary fields use decimal/numeric precision consistent with platform rules (no floating-point for money).

**Story 1.2 — Validation and error reporting on import**

- **Given** my Excel file has schema or business-rule violations, **when** I upload it, **then** I receive a clear list of errors (row/column or field-level where feasible) without silent data corruption.
- **Acceptance criteria**
  - Invalid files do not commit incorrect aggregates; user-visible state matches database state.
  - Error messages are understandable to a Finance user (not raw stack traces for expected validation failures).
  - Duplicate or conflicting imports are handled per agreed rules (see Open Questions).

**Story 1.3 — View imported revenue in a simple UI**

- **Given** data has been loaded successfully, **when** I open the web UI, **then** I can see imported revenue facts in a structured way (e.g., tabular or summarized view scoped to what Phase 1 supports).
- **Acceptance criteria**
  - Authenticated (or agreed dev-mode) access only; no public anonymous access to financial data.
  - Displayed amounts match database values for the same query scope (spot-check reconciliation path exists for Finance).
  - UI supports the minimum workflow: upload → validation feedback → view data.

**Story 1.4 — API and persistence aligned to architecture**

- **Given** the platform exposes APIs for upload and retrieval, **when** clients call them, **then** behavior matches documented contracts and uses UUID primary keys and `NUMERIC(18,4)` for amounts as per project rules.
- **Acceptance criteria**
  - Schema changes go through architectural review before implementation.
  - No hardcoded API keys or model names in code paths introduced in Phase 1.

**Explicitly out of scope for Phase 1**

- Full **natural language / MCP** query experience (Phase 3); optional minimal technical spike only if explicitly approved—not user-facing “CXO NL” scope.
- **Revenue analytics engine**: aggregations across hierarchy, PoP comparisons, materialized views (Phase 2).
- **HubSpot** or any external CRM sync (Phase 4).
- **Forecasting, profitability modeling, segmentation, multi-currency** (Phase 5).
- Enterprise-grade **SSO**, advanced **row-level security** policies, and full **admin** suites—unless listed as Phase 1 must-haves in Open Questions.

---

### Phase 2: Revenue Analytics Engine

**Phase goal:** Enable hierarchical revenue analytics with period-over-period comparisons, filtering, and drill-down, backed by performant structures (e.g., materialized views) for interactive use.

**Business value delivered:** BU Heads and CXOs can analyze revenue by org hierarchy and time with MoM, QoQ, YoY-style comparisons—without exporting everything back to Excel for pivoting.

#### User stories

**Story 2.1 — Aggregate revenue by org hierarchy**

- **Given** revenue facts exist for multiple BUs and divisions, **when** I select a level (org, BU, division), **then** I see totals that roll up correctly at each level.
- **Acceptance criteria**
  - Sums reconcile: child totals sum to parent totals for the same period and filter set.
  - Changing hierarchy scope updates results deterministically.

**Story 2.2 — Period-over-period comparisons**

- **Given** I choose a metric and two periods (or a comparison type such as MoM, QoQ, YoY where supported), **when** I run the comparison, **then** I see both absolute and relative change with clear labeling of periods.
- **Acceptance criteria**
  - Period boundaries are explicit in the UI (no ambiguous “last quarter” without confirmation—Phase 2 may use explicit date/period pickers).
  - If data is missing for a leg of the comparison, the UI states what is missing rather than implying zero revenue.

**Story 2.3 — Filtering and drill-down**

- **Given** I am viewing an aggregate, **when** I apply filters (e.g., BU, division, revenue type, customer) or drill into a row, **then** the detail view reflects the same filters and matches rolled-up totals.
- **Acceptance criteria**
  - Drill-down from summary to detail reconciles to the same source facts as Phase 1 ingestion.
  - Performance meets NFR targets for typical enterprise data volumes (see Section 4).

**Story 2.4 — Performance via precomputed structures**

- **Given** large fact tables, **when** users run common hierarchical and time-series queries, **then** responses stay within performance expectations through materialized views or equivalent.
- **Acceptance criteria**
  - Refresh strategy documented: when views refresh after new loads, and how users are informed if data is stale.
  - No incorrect results due to stale caches—either freshness guarantees or explicit “as of” timestamps.

**Explicitly out of scope for Phase 2**

- **Natural language** query interface and semantic layer (Phase 3).
- **HubSpot** and other external ingestion beyond Excel (Phase 4+).
- **Forecasting, profitability, segmentation, multi-currency** (Phase 5).
- Replacing **Finance-owned** GL; this remains a revenue intelligence layer unless product direction changes.

---

### Phase 3: NL Query Interface

**Phase goal:** Allow business users to ask revenue questions in natural language with a governed path to answers: semantic mapping, validation before execution, disambiguation, and auditability.

**Business value delivered:** CXOs and BU Heads can query revenue in plain language, get validated SQL (or equivalent) execution, and trust that ambiguous questions are clarified rather than guessed.

#### User stories

**Story 3.1 — Map business terms to the semantic layer**

- **Given** I use business vocabulary (e.g., “Q3 revenue by BU”), **when** the system interprets my question, **then** it resolves terms to the canonical schema via an explicit semantic layer.
- **Acceptance criteria**
  - Mappings are maintainable and documented; no silent synonym drift without versioning or change control process (defined in ops, minimal viable in product).
  - OpenAI (or configured) model name is read from settings—never hardcoded.

**Story 3.2 — Validate before execute**

- **Given** a natural language question, **when** the system generates a query plan, **then** it validates safety and correctness rules before execution (e.g., read-only, allowed tables, row limits).
- **Acceptance criteria**
  - Destructive or out-of-scope SQL is rejected.
  - Results are consistent with the same filters run via UI/analytics where both exist.

**Story 3.3 — Disambiguation**

- **Given** my question could refer to multiple periods, BUs, or metrics, **when** I submit it, **then** the system asks clarifying questions instead of returning a wrong answer.
- **Acceptance criteria**
  - At least one user-visible disambiguation path is covered end-to-end (e.g., ambiguous quarter).
  - Logs capture the final resolved interpretation for audit.

**Story 3.4 — Query audit log**

- **Given** an NL query is executed, **when** IT or Finance reviews audit needs, **then** they can see who asked what, when, and the executed query or plan summary.
- **Acceptance criteria**
  - Audit entries are tamper-evident in the sense of standard append-only application logs or DB audit table per design.
  - Retention period aligned with policy (see Open Questions).

**Explicitly out of scope for Phase 3**

- **HubSpot** sync and CRM-backed answers that require live HubSpot as source of truth (Phase 4).
- **New analytics** beyond what Phase 2 delivers unless required to support NL (prefer thin NL over scope creep).
- **Forecasting and advanced modeling** (Phase 5).

---

### Phase 4: HubSpot Integration

**Phase goal:** Connect HubSpot Deals (or agreed objects) via OAuth and incremental sync, mapping external IDs into the canonical revenue model alongside Excel-sourced data.

**Business value delivered:** Revenue intelligence can incorporate CRM pipeline and closed-won data with a governed sync—reducing manual re-keying and improving timeliness for teams that live in HubSpot.

#### User stories

**Story 4.1 — OAuth connection to HubSpot**

- **Given** I am an authorized IT Admin or delegate, **when** I connect HubSpot, **then** OAuth completes securely and tokens are stored per security requirements.
- **Acceptance criteria**
  - Secrets are not hardcoded; use environment/settings.
  - Connection status is visible (connected / error / token refresh failed).

**Story 4.2 — Incremental sync**

- **Given** HubSpot is connected, **when** the sync job runs, **then** new and updated records are ingested incrementally without full reload every time, within agreed limits.
- **Acceptance criteria**
  - Sync failures are retriable and visible; partial failure behavior is documented.
  - No duplicate canonical rows without a defined dedupe key (see Open Questions).

**Story 4.3 — External ID mapping**

- **Given** HubSpot records reference companies, deals, and owners, **when** data lands in the platform, **then** external IDs map to canonical customers, BUs, and revenue classifications per the mapping design.
- **Acceptance criteria**
  - Unmapped entities surface as exceptions for resolution, not silent misclassification.
  - Reconciliation reports or views exist for Finance to compare HubSpot-sourced totals to Excel-sourced totals where both exist.

**Explicitly out of scope for Phase 4**

- **Other CRMs** (Salesforce, Dynamics) unless explicitly added later.
- **Bidirectional sync** (writing back to HubSpot) unless decided otherwise.
- **Full CPQ / billing** replacement; integration is revenue intelligence ingestion, not full revenue operations suite.

---

### Phase 5: Enterprise Intelligence Expansion

**Phase goal:** Extend the platform with forecasting, profitability modeling, customer segmentation, and multi-currency support suitable for enterprise decision-making.

**Business value delivered:** Leaders move from “what happened” to “what might happen next” and “where we earn,” with segmentation and currency handling that match global enterprise reality.

#### User stories

**Story 5.1 — Forecasting**

- **Given** historical revenue and (where required) assumptions, **when** I request a forecast, **then** I receive documented outputs with confidence/assumption disclosure per product rules.
- **Acceptance criteria**
  - Forecast methodology is transparent enough for Finance review (not a black box score).
  - Clear separation from actuals to avoid misleading board-ready views without explicit labeling.

**Story 5.2 — Profitability modeling**

- **Given** cost inputs or allocated costs are available per design, **when** I analyze profitability, **then** margins and contributions are computed with the same precision rules as revenue.
- **Acceptance criteria**
  - Cost allocation rules are explicit; changing allocation method does not silently overwrite history without versioning strategy.

**Story 5.3 — Customer segmentation**

- **Given** revenue and customer attributes, **when** I define or select segments, **then** I can compare segment performance over time.
- **Acceptance criteria**
  - Segment membership rules are reproducible and auditable.

**Story 5.4 — Multi-currency**

- **Given** revenue in multiple currencies, **when** I view consolidated reports, **then** conversion uses defined rates and effective dates, with display of native and reporting currency.
- **Acceptance criteria**
  - Rate source and date are visible for Finance reconciliation.
  - No silent FX without user-visible basis.

**Explicitly out of scope for Phase 5 (unless pulled forward by explicit decision)**

- **General ledger** as system of record.
- **Tax and statutory reporting** as authoritative filings.
- **Real-time streaming** from all enterprise systems—scope remains batch/sync-oriented unless extended later.

---

### Phase 6: Enterprise Identity & Pilot Governance

**Phase goal:** Enable enterprise pilots to use **corporate SSO**, meet **audit and governance** expectations with **exportable evidence**, and run production with **clear IT operational visibility**—without adding new core revenue analytics beyond Phases 1–5.

**Business value delivered:** IT and Security can approve production go-live; Finance and auditors get defensible audit trails; the product matches how enterprises buy and operate software.

**Authoritative detail:** User stories, acceptance criteria, **Approved product decisions** (SSO, JIT, audit export, admin depth, etc.), and **out of scope** items are **locked** in [`phase-6-requirements.md`](phase-6-requirements.md).

#### User stories (summary)

**Story 6.1 — Enterprise SSO (SAML 2.0 / OIDC)**

- **Given** a corporate IdP and pilot expectations for enterprise login, **when** IT Admin configures SSO, **then** users authenticate via **OIDC and/or SAML** per approved sequencing with secure token handling and no hardcoded IdP secrets.

**Story 6.2 — Audit export and retention alignment**

- **Given** governance needs for imports, NL, sync, and security events, **when** an authorized user exports audit data, **then** records are available within the **365-day** operational window (per §5 decision 9) via **authorized export**; automated SIEM streaming remains **out of scope** unless changed by separate decision (see Phase 6 doc).

**Story 6.3 — Enterprise admin — security posture and pilot commitments**

- **Given** dedicated deployment per enterprise customer, **when** IT Admin manages tenant security, **then** **SSO**, **domain allowlist**, **reporting currency visibility**, and related settings are **self-service** where defined in Phase 6—not routine developer-only config.

**Story 6.4 — Operational visibility for integrations and background work**

- **Given** Excel ingest, HubSpot sync, and Celery jobs, **when** IT Admin monitors health, **then** **consolidated** visibility supports **pilot runbooks** without false “green” on partial failures.

**Explicitly out of scope for Phase 6 (see [`phase-6-requirements.md`](phase-6-requirements.md) for full list)**

- **Multi-tenant SaaS** productization; **new** analytics, NL features, or CRM connectors; **full SCIM**; **automated SIEM** streaming; **in-product** legal certification.

---

### Phase 7: Customer Revenue Operations & Standardized Workbook I/O

**Phase goal:** Give operations and delivery leaders **customer-wise** revenue visibility, **hierarchical comparisons** (organization → business unit → division → customer), **discrepancy** handling with **email** to the **delivery manager** and a **variance explanation** experience, and an **Excel-like** matrix with **accessible** green/red **at-a-glance** movement—plus **standardized** import/export aligned to an agreed workbook layout.

**Business value delivered:** Delivery directors work in a familiar spreadsheet-shaped view; Finance and operations share one **canonical** template (see reference [`samples/EUROPE_Weekly Commercial Dashboard.xlsx`](../samples/EUROPE_Weekly%20Commercial%20Dashboard.xlsx)); variances are **accountable** and **auditable**.

**Authoritative detail:** User stories **7.1–7.5**, **Approved product decisions**, reference workbook analysis, and **out of scope** items are **locked** for Phase 7 in [`phase-7-requirements.md`](phase-7-requirements.md). **Architectural** and **database** deltas for implementation are in [`docs/architecture/phase-7-changes.md`](../architecture/phase-7-changes.md) (`@technical-architect`). **Cross-team implementation handoff** (technical lead, UX/UI, QA): [`docs/architecture/phase-7-implementation-handoff.md`](../architecture/phase-7-implementation-handoff.md).

#### User stories (summary)

**Story 7.1 — Customer-wise revenue** — First-class **customer** grain with correct roll-up under **division → BU → org**.

**Story 7.2 — Hierarchical comparison** — Compare revenue **per customer** and **per division** within **BU** under **organization**, with reconciliation to parent totals.

**Story 7.3 — Discrepancies and explanations** — Configurable **rules** surface discrepancies; **email** the **delivery manager** with a link to record a **reason** for **up** or **down** movement; **audited** explanations.

**Story 7.4 — Excel-like grid** — **Delivery director** matrix: **green** / **red** (with non-color cues) for growth / decline vs agreed comparison.

**Story 7.5 — Standardized import/export** — **Canonical** layout: **Sr. No.**, **Customer Name (legal)**, **Customer Name (common)**, **13** monthly columns from **Dec-25** through **Dec-26** pattern; validation and **versioned** template.

**Explicitly out of scope for Phase 7 (see [`phase-7-requirements.md`](phase-7-requirements.md) for full list)**

- Changing **Phases 1–6** locked requirements; Phase 7 builds **on top**.
- **Mandatory** ingest of all auxiliary sheets in the reference workbook beyond agreed **v1** scope.
- Full **workflow** approval chains beyond **explain / audit**.

---

## 4. Non-Functional Requirements

### Performance expectations

- **Interactive UI:** Primary dashboards and drill-downs should respond within **sub–few seconds** for typical queries on expected enterprise fact-table sizes; heavy queries may use async jobs with explicit progress where applicable.
- **Imports:** Excel and sync jobs should complete within agreed windows (define SLAs per environment); long-running jobs must not block the UI without feedback.
- **Analytics (Phase 2+):** Materialized views or equivalent must be sized so common hierarchical and PoP queries remain interactive; explicit refresh cadence and “as of” semantics are required.
- **NL (Phase 3):** Response time includes LLM latency; product should set user expectations (e.g., loading states) and enforce timeouts rather than hang indefinitely.

### Security requirements

- **Secrets:** No hardcoded API keys or tokens; use environment/settings. OpenAI model name from configuration (`.env` / settings), not literals in code.
- **Transport and storage:** TLS for data in transit where applicable; credentials and OAuth tokens stored with appropriate encryption at rest per deployment target.
- **Access control:** Role- or scope-based access aligned to org hierarchy (exact model to be fixed in Open Questions); no anonymous access to financial datasets.
- **Audit:** Query and integration actions auditable (especially NL queries and HubSpot sync events) for IT and Finance governance.
- **Least privilege:** Database and service accounts follow least privilege; read-only execution paths for analytics/NL where possible.

### Data accuracy requirements (financial platform — zero tolerance for wrong numbers)

- **Numeric integrity:** All monetary amounts use **`NUMERIC(18,4)`** (or stricter if Finance mandates); **never `FLOAT`** for money in the database or business logic.
- **Reconciliation:** Any displayed aggregate must be derivable from underlying facts; spot-check and export paths must match DB totals for the same filters.
- **No silent failure:** Import and sync must not report success if rows failed validation in a way that breaks totals; behavior for partial success must be explicit and visible.
- **Single definition of truth:** Metrics (e.g., “revenue”) have one canonical definition in the semantic layer (Phase 3+) and documented formulas for analytics (Phase 2+).
- **Ambiguity:** Where business language is ambiguous, the system must **not** guess in a way that could misstate financial results—clarification or explicit assumptions are required.
- **Quality gate:** Features are not “done” without **Quality Analyst** sign-off per project rules; regression tests cover rounding, FX (when Phase 5 applies), and hierarchy rollups.

---

## 5. Approved product decisions

The following answers were **approved** on **3 April 2026** and supersede any prior “open questions” or working-assumption language. They align with `.cursorrules` (**Phase 1 = Core Schema + Excel Import only**). Together with §3 Phase 1 and §4 NFRs, they constitute the **locked** Phase 1 requirements baseline.

| # | Topic | Approved answer |
|---|--------|-------------------|
| 1 | **Phase 1 NL / MCP** | **No** customer-facing natural language or MCP in Phase 1. NL/MCP is **Phase 3**. Optional non-product smoke tests may use settings-driven OpenAI in dev only—no shipped UX. |
| 2 | **Excel validation** | **Fail entire file** on any row/column validation error (single transactional outcome). No partial commits for Phase 1. |
| 3 | **Overlapping / duplicate imports** | Each successful load is an **import batch** with immutable batch id. **Default:** if new file would insert facts that **overlap** an existing batch’s scope (same tenant + agreed grain, e.g. org + period), **reject** unless the user explicitly requests **replace**. **Replace** = delete prior facts for that scope within one transaction, then insert new rows (audited). |
| 4 | **Identity & access (Phase 1–2)** | **Application auth** (e.g. JWT + email/password or service API key for automation) for MVP. **SSO (SAML/OIDC)** planned after core value is proven unless a pilot mandates it. **Row-level BU scoping** required by **Phase 2** when hierarchy analytics ship; Phase 1 may be **tenant-wide** for pilot users. |
| 5 | **Excel vs HubSpot (Phase 4)** | **Excel (and manual adjustments in-app) is authoritative for booked revenue actuals** in scope. HubSpot contributes **pipeline / CRM** facts; it **must not silently overwrite** Excel-derived actuals for the same canonical key. Conflicts **surface in a reconciliation / exception view** for Finance. |
| 6 | **HubSpot v1 scope (Phase 4)** | **Deals** primary: deal id, amount, close date, pipeline/stage, association to **company**; map to `dim_customer` / hierarchy via configurable mapping tables. Detailed field list fixed in Phase 4 design doc. |
| 7 | **Multi-currency (Phase 5)** | **Single reporting currency** per tenant (default **USD**) with an **FX rate table** (effective date, rate). **Initial rates:** manual admin upload; optional rate API later. |
| 8 | **Forecasting (Phase 5)** | **Hybrid:** support **imported** forecasts from Finance (preferred for liability) plus optional **simple statistical** baseline from history. **UI disclaimer:** forecast is informational, not audited financials. |
| 9 | **Audit retention** | **Operational default:** application audit events (imports, NL queries when Phase 3 exists) retained **365 days** in primary store; **long-term** archive policy subject to **legal/compliance** sign-off (see §6). |
| 10 | **Deployment model** | **First enterprise customer:** **dedicated deployment** (single-tenant style: isolated DB and app instance per customer) to simplify compliance and reduce cross-tenant risk. **Multi-tenant SaaS** remains a later productization option. |
| 11 | **Schema governance** | **`@technical-architect` approval** required for any schema change per project rules. **Finance freeze windows:** no prod migrations during customer-declared freeze without written exception. |
| 12 | **Celery / Redis (Phase 1)** | **Async:** Excel files over a **size or row threshold** (exact thresholds TBD in implementation, e.g. 5 MB or 100k rows). **Timeouts:** worker **hard cap 30 minutes** per job; **3 retries** with backoff for transient failures. Small files run synchronously for simpler UX. |

---

## 6. Pending stakeholder sign-off

These items remain **subject to legal, enterprise sales, or pilot customer** confirmation. They **do not override** the Phase 1 lock for scope defined in §3 Phase 1, §4, and §5 unless a formal change request updates this document.

- **Jurisdiction-specific retention** (GDPR, sector rules) and **exact** audit log retention beyond the 365-day operational default.
- **Pilot contract** commitments: SSO deadline, single- vs multi-tenant, and **reporting currency** if not USD.
- **Finance calendar** blackout dates for production releases and migrations.

---

*This document is the product-level contract for phased delivery. Technical schema and API design must align with `@technical-architect`; implementation with `@tech-lead`; UX with `@ux-ui-designer`; quality with `@quality-analyst`.*

**Revision history:**

| Date | Change |
|------|--------|
| 3 April 2026 | Document APPROVED; Phase 1 requirements locked; §5 finalized as approved product decisions. |
| 6 April 2026 | **Phase 6** added to Section 3 (Enterprise Identity & Pilot Governance); pointer to **approved** [`phase-6-requirements.md`](phase-6-requirements.md); status block updated. |
| 8 April 2026 | **Phase 7** added to Section 3 (Customer Revenue Operations & Standardized Workbook I/O); pointer to **approved** [`phase-7-requirements.md`](phase-7-requirements.md), [`docs/architecture/phase-7-changes.md`](../architecture/phase-7-changes.md), and [`docs/architecture/phase-7-implementation-handoff.md`](../architecture/phase-7-implementation-handoff.md); **Phases 1–6** text unchanged in substance. |
