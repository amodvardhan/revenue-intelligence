# Phase 4 Requirements — HubSpot Integration

| Field | Value |
|--------|--------|
| **Document status** | **APPROVED** |
| **Approval date** | **6 April 2026** |
| **Approved by** | Product Owner |
| **Parent document** | [`product-requirements.md`](product-requirements.md) (Section 3 — Phase 4; Section 4 — NFRs; Section 5 — approved decisions) |
| **Phase 4 lock** | **LOCKED** — Requirements in this document are frozen for Phase 4 execution as of the approval date. Implementation, QA, and design SHALL align with this baseline. Scope, acceptance criteria, or material changes require a **written change request** and **Product Owner re-approval** (updated status block and revision note). |
| **Depends on** | Phase 3 complete and QA sign-off per [`docs/qa/phase-3-report.md`](../qa/phase-3-report.md) |

---

## Phase goal (one sentence)

**CRM-sourced revenue intelligence lands in the platform through a secure HubSpot connection, incremental sync, and explicit mapping into the canonical model—alongside Excel—without silently overriding Finance-owned actuals.**

### Excel vs Phase 7 workbook (scope)

**Excel** in Story 4.3 and in reconciliation means **Phase 1** spreadsheet ingestion into `fact_revenue` (locked rules in the ingestion validator), not the **Phase 7** standardized customer-matrix workbook (`Sheet1` / EUROPE reference in [`phase-7-requirements.md`](phase-7-requirements.md)). That template interop is **optional** and gated by **`ENABLE_PHASE7`**; it is not a Phase 4 deliverable.

---

## What Phase 3 delivered that Phase 4 builds on

Phase 3 shipped the **natural-language query interface** on top of Phase 2 analytics: a **maintained semantic layer** with versioning/traceability, **validate-before-execute** safety (read-only paths, envelopes, no raw destructive SQL), **disambiguation** when intent is ambiguous, and an **append-only query audit log** with role-appropriate access. Phase 4 **adds HubSpot as a governed ingestion source** so pipeline and CRM-aligned facts can exist in the same canonical schema and eventually be addressable through the same **hierarchical analytics and NL** paths—subject to **source-of-truth rules** (Excel remains authoritative for booked actuals where the PRD says so; HubSpot contributes **pipeline / CRM** dimensions and must **surface conflicts** rather than overwrite). Phase 3 **audit and security NFRs** extend naturally to **integration events** (connect, sync, token health) per parent PRD Section 4.

---

## User stories — Phase 4 only

Stories are numbered **4.1–4.3** to align with [`product-requirements.md`](product-requirements.md). Format: **Given / When / Then**.

### Story 4.1 — OAuth connection to HubSpot

**Given** I am an authorized IT Admin or delegate, **when** I connect HubSpot for my tenant, **then** OAuth completes securely, tokens are stored per security requirements, and I can see whether the integration is healthy.

**Acceptance criteria**

- **Secrets and tokens** are not hardcoded; HubSpot app credentials and token storage use **environment / settings** (parent PRD Section 4 — Secrets).
- **Connection status** is visible in the UI or admin surface: at minimum **connected**, **error**, and **token refresh failed** (or equivalent) so operators are not blind to auth drift.
- **Least privilege** HubSpot scopes are used for the agreed v1 object set (see parent PRD §5 decision 6 — **Deals** primary).
- **Transport and storage** align with parent PRD Section 4 (TLS in transit; tokens at rest per deployment target).

---

### Story 4.2 — Incremental sync

**Given** HubSpot is connected, **when** the sync job runs on a defined schedule or manual trigger, **then** new and updated HubSpot records are ingested **incrementally** (not a full wipe/reload every run by default), within API and operational limits, with visible outcomes for success and failure.

**Acceptance criteria**

- **Incremental behavior** is documented: cursor, `lastmodified`-style semantics, or equivalent—so routine syncs do not require full-table re-fetch unless a **reconciliation / repair** path is explicitly invoked.
- **Failures are retriable** where appropriate; **partial failure** behavior is **documented** (what commits, what retries, what surfaces to the user).
- **No silent success** when material rows failed validation in a way that breaks totals (parent PRD Section 4 — Data accuracy).
- **Long-running work** does not block the main UI without feedback where jobs are async (parent PRD Section 4 — Imports / sync jobs; Celery baseline from §5 decision 12 as applicable).
- **Auditability:** sync events (start, end, error summary) are available for IT/Finance governance (parent PRD Section 4 — Audit for integration actions).

---

### Story 4.3 — External ID mapping and reconciliation

**Given** HubSpot records reference companies, deals, owners, and pipelines, **when** data lands in the platform, **then** external identifiers map to **canonical customers, hierarchy, and revenue classifications** per an agreed mapping design, and **Finance can reconcile** HubSpot-sourced totals against Excel-sourced actuals where both exist.

**Acceptance criteria**

- **v1 scope** follows parent PRD §5 decision 6: **Deals** primary—deal id, amount, close date, pipeline/stage, association to **company**; map to `dim_customer` / hierarchy via **configurable mapping tables** (detailed field list fixed in Phase 4 design doc).
- **Unmapped or ambiguous entities** surface as **exceptions for resolution**, not silent misclassification (parent PRD Phase 4 story text).
- **Excel vs HubSpot authority** follows parent PRD §5 decision 5: **Excel (and manual adjustments in-app) is authoritative for booked revenue actuals** in scope; HubSpot **must not silently overwrite** Excel-derived actuals for the same canonical key; **conflicts surface** in a **reconciliation / exception view** for Finance.
- **Dedupe and identity:** no duplicate canonical facts without a **defined dedupe key** (parent PRD open question—resolved in design; see architect decisions below).
- **Reconciliation:** views or reports exist so Finance can **compare** HubSpot-sourced aggregates to Excel-sourced aggregates **where both exist** (parent PRD Phase 4).

---

## Explicitly out of scope for Phase 4

Per [`product-requirements.md`](product-requirements.md) Phase 4:

- **Other CRMs** (Salesforce, Microsoft Dynamics, etc.) unless explicitly added by a future change request.
- **Bidirectional sync** (writing back to HubSpot) unless the Product Owner approves a scoped exception—default is **ingestion-only** for v1.
- **Full CPQ, billing, or subscription lifecycle** replacement; integration is **revenue intelligence ingestion**, not a full revenue operations suite.
- **Forecasting, profitability, segmentation, multi-currency** as net-new product pillars (**Phase 5**), except where a minimal field display is required for mapping context.
- **New NL semantics** beyond what is needed to **safely include** CRM-sourced facts in existing analytics/NL paths—prefer **thin integration** over expanding the semantic layer speculatively (align with Phase 3 “thin NL” discipline).
- **Full enterprise SSO** as a Phase 4 gate—application auth remains baseline per parent PRD §5 unless a **pilot contract** mandates otherwise.

---

## Decisions that need architect input before we proceed

These items should be resolved in design review (**`@technical-architect`** per parent PRD Section 5 — schema governance) before locking Phase 4 implementation:

1. **HubSpot auth model** — OAuth app type (single app vs per-tenant), **token rotation**, **refresh failure** handling, and **secret storage** (env, vault) aligned to dedicated-deployment assumptions in §5 decision 10.
2. **Sync architecture** — Celery (or equivalent) **queues**, **scheduling**, **idempotency**, **rate-limit** handling with HubSpot APIs, and **backfill vs incremental** first-run strategy.
3. **Canonical schema delta** — New tables/columns for **external IDs**, **sync cursors**, **raw staging** vs **typed facts**, and **migration** strategy with Finance freeze windows (§5 decision 11).
4. **Dedupe and grain** — The **business key** for deal-derived facts vs Excel facts; **upsert** semantics; **soft-delete** when a deal disappears in HubSpot.
5. **Conflict detection** — How “same canonical key” is detected for **Excel vs HubSpot** (tenant rules, time windows, customer match confidence)—implementation of §5 decision 5 without silent overwrite.
6. **Observability** — Metrics and logs for sync health; **correlation ids** from UI → worker → HubSpot → DB; alignment with Phase 3 audit patterns where appropriate.
7. **NL and analytics inclusion** — How CRM-sourced rows participate in **Phase 2 rollups** and **Phase 3 NL** (filters by source, labels, or separate measures)—avoid double-counting and ambiguous “revenue” definitions.

---

## Open questions for the Product Owner

Please confirm or adjust the following so engineering and QA can lock acceptance tests:

1. **Who may connect HubSpot?** Is it strictly **IT Admin**, or may **Finance** connect with IT approval? Any **segregation of duties** requirement for OAuth vs mapping configuration?
2. **Initial sync scope:** On first connect, should we **pull all historical open + closed-won deals** (subject to API limits), or only a **rolling window** (e.g., last 24 months)? Any **pilot-specific** cap?
3. **Sync frequency:** Expected default (**hourly / daily / manual-only** for v1) and whether **manual sync** is mandatory for the first release.
4. **Deal amount semantics:** Is **Deal amount** in HubSpot accepted as **pipeline / CRM revenue** for v1, or must amounts map only after a **stage gate** (e.g., closed-won only)? Any **exclude** lists (internal deals, test pipelines)?
5. **Reconciliation UX minimum:** Is a **read-only report/export** sufficient for v1, or is **in-app exception workflow** (assign, comment, resolve) required for launch?
6. **Non-English HubSpot data:** Are **company and deal names** allowed to contain non-ASCII; any **PII** constraints for logs and audit (names in clear text vs hashed)?
7. **HubSpot sandbox:** Will the pilot provide a **dedicated HubSpot developer/test portal** for CI and demos, or is **mocked integration** acceptable for automated tests?

---

*Aligned to [`product-requirements.md`](product-requirements.md). UX alignment with `@ux-ui-designer`; quality gates with `@quality-analyst`; schema changes with `@technical-architect`.*

**Revision history:**

| Date | Change |
|------|--------|
| 6 April 2026 | Initial Phase 4 requirements draft from parent PRD Phase 4; depends on Phase 3 QA GO per `docs/qa/phase-3-report.md`. |
| 6 April 2026 | Document **APPROVED** by Product Owner; Phase 4 requirements **LOCKED**. |
