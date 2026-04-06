# Phase 3 Requirements — NL Query Interface

| Field | Value |
|--------|--------|
| **Document status** | **APPROVED** |
| **Approval date** | **6 April 2026** |
| **Approved by** | Product Owner |
| **Parent document** | [`product-requirements.md`](product-requirements.md) (Section 3 — Phase 3; Section 4 — NFRs; Section 5 — approved decisions) |
| **Phase 3 lock** | **LOCKED** — Requirements in this document are frozen for Phase 3 execution as of the approval date. Implementation, QA, and design SHALL align with this baseline. Scope, acceptance criteria, or material changes require a **written change request** and **Product Owner re-approval** (updated status block and revision note). |
| **Depends on** | Phase 2 complete and QA sign-off per [`docs/qa/phase-2-report.md`](../qa/phase-2-report.md) |

---

## Phase goal (one sentence)

**Business users can ask revenue questions in plain language and receive governed, auditable answers—via a maintained semantic layer, safe read-only execution, disambiguation when intent is unclear, and query audit trails for IT and Finance.**

---

## What Phase 2 delivered that Phase 3 builds on

Phase 2 shipped the **revenue analytics engine**: **hierarchical rollups** (org → BU → division) with **reconciling totals**, **period-over-period comparisons** (explicit periods, missing-leg semantics, no false precision), **filters and drill-down** from summary to `fact_revenue`-aligned detail, **row-level BU scoping** on analytics and revenue APIs, **`GET /auth/me`** business-unit scope, **materialized or equivalent precomputed structures** with **documented refresh and freshness** (`analytics_refresh_metadata`, ingest hooks), and a **customer-facing analytics UI** (`AnalyticsPage`) aligned to those APIs. Phase 3 **reuses the same canonical definitions of revenue and dimensions** so natural-language answers **match** UI/analytics results where both paths exist—adding interpretation, safety gates, clarification flows, and **audit** rather than new competing metrics.

---

## User stories — Phase 3 only

Stories are numbered **3.1–3.4** to align with [`product-requirements.md`](product-requirements.md). Format: **Given / When / Then**.

### Story 3.1 — Map business terms to the semantic layer

**Given** I use everyday business vocabulary (for example “Q3 revenue by BU” or “year-over-year change for my division”), **when** the system interprets my question, **then** it resolves terms to the **canonical schema and metrics** through an explicit **semantic layer** (not ad-hoc string substitution).

**Acceptance criteria**

- Mappings are **maintainable and documented**; changes to synonyms or metric definitions follow a **minimal viable** change-control path (versioning or equivalent—enough that Finance can trust what “revenue” means in NL).
- **No silent synonym drift:** undocumented changes do not alter interpretation without traceability agreed in design.
- **OpenAI (or configured) model identifier** is read from **settings / environment**—**never** hardcoded in application code paths (per parent PRD Section 4 and §5).
- Resolved interpretation is **consistent** with Phase 2 analytics definitions for the same filters and periods where NL and UI both apply.

---

### Story 3.2 — Validate before execute

**Given** I have submitted a natural-language question, **when** the system produces a query plan (for example generated SQL or an internal plan bound to allowed operations), **then** it **validates safety and correctness** before execution.

**Acceptance criteria**

- **Read-only** execution path for NL-driven queries; **destructive** or out-of-scope operations are **rejected** with a user-appropriate message (not raw stack traces for expected failures).
- **Allowed scope** is enforceable (for example permitted tables/views, **row limits**, timeout bounds) per design—**least privilege** aligned with parent PRD Section 4.
- Results for a given interpretation **reconcile** to the same logical outcome as the **Phase 2 analytics / revenue APIs** where both exist (single definition of truth—parent PRD Section 4).

---

### Story 3.3 — Disambiguation

**Given** my question could refer to **multiple** periods, business units, metrics, or comparison types, **when** I submit it, **then** the system **asks clarifying questions** or presents explicit choices **instead of guessing** a financially material interpretation.

**Acceptance criteria**

- At least **one** end-to-end **user-visible** disambiguation path is implemented and testable (for example ambiguous quarter or fiscal vs calendar if both are in scope for the pilot).
- **No silent guess** that could misstate revenue or comparisons (aligns with parent PRD Section 4 — ambiguity).
- **Logs or audit artifacts** capture the **final resolved interpretation** alongside the executed plan (feeds Story 3.4).

---

### Story 3.4 — Query audit log

**Given** a natural-language query is executed, **when** IT Admin or Finance needs to review **who asked what** for governance, **then** they can retrieve **who**, **when**, **what was asked**, and **the executed query or plan summary** (as designed).

**Acceptance criteria**

- Audit entries are **append-only** per agreed design (**tamper-evident** in the standard application sense: no casual in-place edits in primary store).
- **Retention** defaults to **365 days** in primary store for operational events unless **legal/compliance** specifies otherwise (parent PRD §5 decision 9; long-term archive per §6 pending sign-off).
- Access to audit views is **authenticated** and **role-appropriate** (no anonymous access to financial or audit data).

---

## Explicitly out of scope for Phase 3

Per [`product-requirements.md`](product-requirements.md) Phase 3:

- **HubSpot** (or any CRM) **sync** and answers that require **live HubSpot** as source of truth (**Phase 4**).
- **New analytics capabilities** beyond what Phase 2 already delivers **unless** strictly required to expose NL on top of existing rollup/compare/drill-down (prefer **thin NL** over scope creep).
- **Forecasting, profitability modeling, advanced segmentation, multi-currency** (**Phase 5**).
- **Full enterprise SSO** as a Phase 3 gate: application auth remains the baseline per §5 unless a **pilot contract** mandates otherwise—Phase 3 should **not** block on full IdP integration unless explicitly added by change request.
- **Customer-facing MCP** product UX was explicitly deferred from Phase 1; Phase 3 scope for **MCP** (if any) should be **confirmed** in architect review—see below—not assumed as a parallel full product surface unless PO approves.

---

## Decisions that need architect input before we proceed

These items should be resolved in design review (**`@technical-architect`** per parent PRD Section 5 and schema governance) before locking Phase 3 implementation:

1. **Semantic layer shape** — Where definitions live (database tables, repo artifacts, or hybrid), **how they version**, and how they bind to **existing** Phase 2 analytics logic (reuse service layer vs. duplicate paths).
2. **Execution strategy** — NL → **generated SQL** vs. NL → **structured calls** into `analytics` / `revenue` services; implications for **validation**, **testability**, and **reconciliation** with Story 2.x behavior.
3. **Safety envelope** — Allowlist of relations/columns, **max rows**, **statement timeout**, and whether execution uses a **dedicated read-only DB role** or equivalent.
4. **LLM integration** — **Sync vs. async** UX, **timeouts** and user messaging (parent PRD Section 4 NL NFR), **rate limiting** and failure modes when the model is unavailable.
5. **Audit persistence** — Schema for **append-only** NL audit events (tables vs. log pipeline), **PII** handling in prompts, and **correlation ids** from UI → worker → DB.
6. **MCP (optional)** — If Python MCP SDK is in scope for Phase 3, clarify **server boundaries**, **authn/z**, and whether MCP is **internal/admin** vs. **end-user**—to avoid duplicating or bypassing Story 3.2 rules.

---

## Follow-up decisions (non-blocking)

These refine Phase 3 delivery and may be resolved during design or pilot onboarding. They **do not** override scope above unless captured in a change request.

1. **Minimum viable NL surfaces:** Chat panel in existing app vs. dedicated page; **mobile** support or desktop-first only for v1.
2. **Disambiguation depth:** Which ambiguity types beyond **quarter/period** ship in v1 (for example BU vs division naming collisions).
3. **Export:** Whether NL results can be **exported** in Phase 3 or deferred.
4. **Localization:** English-only v1 vs. multi-language prompts and UI.

---

*Aligned to [`product-requirements.md`](product-requirements.md). UX alignment with `@ux-ui-designer`; quality gates with `@quality-analyst`.*

**Revision history:**

| Date | Change |
|------|--------|
| 6 April 2026 | Initial Phase 3 requirements draft from parent PRD Phase 3; depends on Phase 2 QA GO per `docs/qa/phase-2-report.md`. |
| 6 April 2026 | Document **APPROVED** by Product Owner; Phase 3 requirements **LOCKED**. |
