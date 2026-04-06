# Phase 5 Requirements — Enterprise Intelligence Expansion

| Field | Value |
|--------|--------|
| **Document status** | **APPROVED** |
| **Approval date** | **6 April 2026** |
| **Approved by** | Product Owner |
| **Parent document** | [`product-requirements.md`](product-requirements.md) (Section 3 — Phase 5; Section 4 — NFRs; Section 5 — approved decisions) |
| **Phase 5 lock** | **LOCKED** — Requirements in this document are frozen for Phase 5 execution as of the approval date. Implementation, QA, and design SHALL align with this baseline. Scope, acceptance criteria, or material changes require a **written change request** and **Product Owner re-approval** (updated status block and revision note). |
| **Depends on** | Phase 4 complete and QA sign-off per [`docs/qa/phase-4-report.md`](../qa/phase-4-report.md) |

---

## Phase goal (one sentence)

**Leaders can move from historical actuals to forward-looking and dimensional insight—forecasts, profitability views, customer segments, and multi-currency consolidation—with definitions and disclosures suitable for enterprise Finance review.**

---

## What Phase 4 delivered that Phase 5 builds on

Phase 4 shipped a **governed HubSpot path**: **OAuth** with visible connection health, **incremental sync** (with documented repair/reconciliation modes), **async job** semantics and **sync audit** visibility, **configurable external-ID mapping** with **exceptions** for unmapped entities, and **Excel vs HubSpot authority**—**conflicts and reconciliation** (including aggregate comparison where both sources exist) without HubSpot **silently overwriting** Finance-owned booked actuals. The platform already combines **Excel ingestion**, **hierarchical analytics** (Phase 2), **NL query** with semantic and audit trails (Phase 3), and **CRM-sourced facts** in the same canonical model.

Phase 5 **extends** that foundation with **new metric classes and dimensions** (forecast, cost/margin, segment membership, FX conversion) that must **compose cleanly** with existing **actuals**, **source labeling** (Excel vs HubSpot vs future sources), **analytics APIs**, and **NL**—without double-counting, silent FX, or ambiguous “revenue” vs “forecast” labeling. Parent PRD **§5 decisions 7 and 8** (multi-currency and forecasting approach) are **binding inputs** for this phase unless revised by formal change request.

---

## User stories — Phase 5 only

Stories are numbered **5.1–5.4** to align with [`product-requirements.md`](product-requirements.md). Format: **Given / When / Then**.

### Story 5.1 — Forecasting

**Given** historical revenue exists in the platform and (where applicable) Finance-supplied forecast inputs or assumptions are available, **when** I request a forward-looking revenue view, **then** I receive outputs whose **methodology and limitations are explicit**—separating **actuals** from **forecast** and surfacing assumptions or disclaimers per product rules.

**Acceptance criteria**

- **Hybrid approach** per parent PRD §5 decision 8: the product supports **imported forecasts from Finance** (preferred for liability and audit alignment) **and**, where approved in design, a **simple statistical baseline** derived from history—with **clear labeling** of which mode produced a given series.
- **Forecast is informational:** prominent **UI disclaimer** that forecast views are **not** audited financial statements unless Finance explicitly exports/signs off outside the product (align with §5 decision 8).
- **No misleading board-ready views:** consolidated screens that mix actuals and forecast use **explicit period boundaries**, **visual or textual separation**, and **no implication** that forecast equals actual.
- **Transparency for Finance review:** enough **methodology disclosure** (inputs, horizon, revision/version if imported, model family if statistical) that Finance can challenge or reconcile—not an unexplainable “black box score.”
- **Numeric integrity:** forecast amounts stored and displayed with **NUMERIC-grade** rules consistent with parent PRD Section 4 (no float for money); units and **currency** behavior align with Story 5.4 when multi-currency applies.
- **Versioning / immutability:** changing imported forecast files or allocation assumptions does **not silently overwrite** prior published forecast versions without a **defined** versioning or effective-dating strategy (align with parent PRD Phase 5 profitability story intent).

---

### Story 5.2 — Profitability modeling

**Given** revenue facts exist and **cost inputs or allocated costs** are available per agreed design, **when** I analyze profitability (e.g., margin or contribution), **then** margins and contributions are computed with the **same precision rules as revenue** and **allocation rules remain explicit and traceable**.

**Acceptance criteria**

- **Cost data model** is explicit: source of costs (import, manual entry, allocated from pools—**per design**), **grain** (match to revenue facts vs higher-level allocation), and **NUMERIC** storage for monetary amounts.
- **Allocation rules are documented** in product/technical design: basis (e.g., by revenue, headcount, driver), **effective dates**, and **who can change** them; changes do **not** silently rewrite historical allocated results without **versioning or audit** (parent PRD Phase 5).
- **Reconciliation path:** Finance can trace displayed margin or contribution **back to underlying revenue and cost lines** for a defined scope (spot-check and export aligned with parent PRD Section 4).
- **Scope clarity:** profitability views state **what costs are included** (COGS vs full loaded, etc.) so CXO/BU narratives are not ambiguous—exact taxonomy is a **design decision** (see architect section below).

---

### Story 5.3 — Customer segmentation

**Given** revenue facts and **customer / dimension attributes** available in the platform, **when** I define or select segments and compare performance over time, **then** segment membership is **reproducible**, **auditable**, and **consistent** with analytics and NL where both apply.

**Acceptance criteria**

- **Segment definition rules** are stored and **replayable** (same inputs yield same membership for a given “as of” date)—no ad-hoc hidden filters.
- **Time behavior is explicit:** whether membership is **snapshot per period**, **slowly changing**, or **point-in-time** from attributes—documented so MoM/QoQ comparisons are not misleading.
- **Hierarchy and access:** segment views respect **existing org/BU scoping** (Phase 2+) so users do not see out-of-scope customers.
- **Integration with NL (Phase 3):** if segments are exposed to natural language, **semantic definitions** align with UI/analytics (no silent synonym drift); ambiguous segment questions trigger **disambiguation** per Phase 3 patterns.
- **Audit:** material changes to segment definitions or rule versions are **traceable** for governance (minimal viable: who/when/what changed).

---

### Story 5.4 — Multi-currency

**Given** revenue (and other monetary facts as scoped in design) exist in **multiple currencies**, **when** I view consolidated reports in the **tenant reporting currency**, **then** conversion uses **defined rates and effective dates**, and both **native** and **reporting-currency** amounts are available for Finance reconciliation.

**Acceptance criteria**

- **Single reporting currency per tenant** with default **USD** unless pilot contract specifies otherwise (parent PRD §5 decision 7).
- **FX rate table** with **effective date** (and rate source **label**—manual upload v1 per §5 decision 7); **no silent FX** without user-visible **basis** (rate date, pair, reporting currency).
- **Display:** consolidated views show **reporting currency** with access to **native currency** and **FX metadata** needed for Finance reconciliation (parent PRD Phase 5 and Section 4 NFRs on FX when Phase 5 applies).
- **Analytics and rollups:** hierarchical and PoP comparisons in reporting currency are **mathematically consistent** with stored rates for the chosen periods; **rounding** behavior documented and covered by regression tests per parent PRD Section 4 **Quality gate**.
- **Optional rate API** remains **out of scope for v1** unless explicitly pulled in by change request (§5 decision 7)—manual upload path must be complete first.

---

## Explicitly out of scope for Phase 5

Per [`product-requirements.md`](product-requirements.md) Phase 5 and Section 4:

- **General ledger** as system of record or automated statutory tie-out.
- **Tax and statutory reporting** as authoritative filings from this product.
- **Real-time streaming** from all enterprise systems—scope remains **batch / sync–oriented** unless extended by a later phase.
- **Full replacement** of Finance-owned planning tools (e.g., enterprise EPM); Phase 5 delivers **in-platform** forecast and profitability **capabilities** aligned to PRD, not full FP&A suite parity unless explicitly added later.
- **New CRMs beyond HubSpot** (Phase 4 scope); Phase 5 does not require Salesforce/Dynamics connectors.
- **Bidirectional CRM writeback** (remains out of scope unless Product Owner approves a separate initiative).

---

## Decisions that need architect input before we proceed

These items should be resolved in design review (**`@technical-architect`** per parent PRD Section 5 — schema governance) before locking Phase 5 implementation:

1. **Schema additions** — Tables/columns for **forecast series** (imported vs generated), **cost lines** and **allocations**, **segment definitions** and **membership**, **FX rates** (pair, effective date, tenant reporting currency), and migrations with **Finance freeze windows** (§5 decision 11).
2. **Forecast storage and versioning** — How imported forecast files bind to **periods**, **scenarios**, and **immutability**; whether **statistical baselines** are persisted and how they refresh.
3. **Profitability grain** — Join model between **fact_revenue** (and HubSpot-sourced rows) and **cost facts**; handling of **partial periods** and **cross-BU allocations**.
4. **Multi-currency application order** — Whether conversion happens at **fact ingest**, **report time**, or **layered** (with explicit “as of” for rates); impact on **Phase 2 materialized** paths and **refresh** semantics.
5. **Segmentation engine** — Rule language (SQL-like vs UI builder), **materialized** segment membership vs on-the-fly, and performance for enterprise volumes (parent PRD Section 4).
6. **NL and semantic layer** — How **forecast**, **margin**, **segment**, and **FX-adjusted** measures enter the **semantic bundle** without breaking **validate-before-execute** and **disambiguation** (Phase 3); **new audit event types** for forecast/cost/FX-sensitive queries.
7. **Double-counting and definition of “revenue”** — Ensure **forecast** and **actuals** are **never** summed without explicit user intent; CRM pipeline vs booked actuals rules from Phase 4 **carry forward**.

---

## Open questions for the Product Owner

Please confirm or adjust the following so engineering and QA can lock acceptance tests and UX:

1. **Phase 5 priority order** — Should all four pillars (**5.1–5.4**) ship in one release, or is a **sequenced** MVP (e.g., multi-currency + forecasting first) required for the first pilot?
2. **Forecast horizon and granularity** — Expected **months/quarters** ahead, **revision cadence**, and whether **scenario** labels (base / upside / downside) are **mandatory** for v1.
3. **Imported forecast format** — Will Finance standardize on **Excel/CSV template** only, or **API upload**—and **who** may upload (Finance-only vs BU)?
4. **Statistical forecast** — Minimum viable **simple statistical** method (e.g., trailing average, naive growth) if included: **acceptable** to Finance for internal views only, or **defer** until imported-only is stable?
5. **Profitability v1 depth** — Is **gross margin** (revenue minus a single cost layer) sufficient for v1, or is **fully loaded** contribution required— and **where** do costs originate (new ingest only vs integration)?
6. **Cost ingest authority** — Same **batch / immutability** rules as revenue imports, or different **correction** workflow?
7. **Segments** — Are segments **global** per tenant, **owned by BU**, or **both**; any **limit** on concurrent segment definitions?
8. **Reporting currency** — Confirm **default USD** per §5 decision 7 for first enterprise customer; any **pilot mandate** for non-USD reporting currency only?
9. **FX rate ownership** — **Who** uploads rates (Finance vs IT), **frequency**, and whether **historical restatement** (re-run consolidations when rates change) is **in scope** for v1.
10. **Pilot and compliance** — Any **jurisdiction** constraints on storing **forecast**, **cost**, or **segment** data that affect **retention** or **fields shown** (see parent PRD §6)?

---

*Aligned to [`product-requirements.md`](product-requirements.md). UX alignment with `@ux-ui-designer`; quality gates with `@quality-analyst`; schema changes with `@technical-architect`.*

**Revision history:**

| Date | Change |
|------|--------|
| 6 April 2026 | Initial Phase 5 requirements draft from parent PRD Phase 5; depends on Phase 4 QA GO per `docs/qa/phase-4-report.md`. |
| 6 April 2026 | Document **APPROVED** by Product Owner; Phase 5 requirements **LOCKED**. |
