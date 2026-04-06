# UX Decisions & Rationale — Phase 1

| Field | Value |
|--------|--------|
| **Status** | **Approved (PO)** — 2026-04-03 |
| **Purpose** | Explain *why* the Phase 1 UX is shaped this way; support alignment with Tech Lead and QA |
| **Revision** | 2026-04-03 — PO review closure: PRD §5 alignment, batch history, initiator, export scope, registration. |

---

## Alignment with product requirements (PRD)

- **Fail entire file:** Story 1.1 still contains legacy wording about “partial success” in acceptance criteria; **approved product decision §5 #2** supersedes it. UX and implementation SHALL treat **fail entire file** as the only Phase 1 behavior.
- **Import batch history** is required for Finance traceability (personas: batches, who loaded what). Documented in `user-flows.md` and `component-specs.md` (`ImportBatchHistory`).

---

## 1. Information architecture and layout

### Decision: Single app shell with **sidebar + main content**

**Why this layout**

- Phase 1 has only two primary destinations (**Import**, **Revenue**); a **left sidebar** scales to Phase 2+ without relearning.
- Finance users expect **enterprise app** patterns (similar to ERP/banking tools), not marketing-style single-page scroll.

**UX principle:** *Consistency + mental model match* — navigation stays visible; users never wonder how to return to import.

**Alternatives considered**

- **Top-only tabs:** Rejected — weak for growth beyond 3–4 sections; less standard for dense data apps.
- **Wizard-only (no separate Revenue):** Rejected — Story 1.3 requires a **dedicated view** of imported facts; burying it inside import reduces audit confidence.

### Decision: **Import** as default landing after login when no data exists; otherwise configurable default (e.g. last route)

**Why:** Reduces time-to-value for empty tenants; returning users may prefer **Revenue**—product can persist “last visited” in local storage.

**UX principle:** *Progressive disclosure* — empty state pushes one clear action; experienced users skip via sidebar.

**Alternatives considered**

- **Always land on Revenue:** Rejected for empty tenants — weaker onboarding without a prominent empty state.

---

## 2. Visual language: color

### Decision: **Teal primary** on **cool neutral** surfaces (slate family)

**Why these colours**

- **Teal** reads “analytical / trustworthy” without the aggressive connotations of pure blue in some enterprise contexts; distinct from generic “AI purple” if NL ships later.
- **Slate neutrals** keep focus on **tabular data**; warm grays compete with warning/amber semantics.

**UX principle:** *Aesthetic-usability effect* — professional palette increases perceived reliability for financial data.

**Alternatives considered**

- **Navy + gold (boardroom):** Rejected for Phase 1 — higher brand design cost; teal/slate is implementable from tokens day one.
- **Pure grayscale:** Rejected — insufficient hierarchy for primary CTAs and error/success.

### Decision: **Semantic red/green** reserved for **status**, not for styling individual revenue cells

**Why:** Color-only profit/loss cues fail **WCAG** and cultural interpretation; Finance needs **numbers** and **labels** first.

**UX principle:** *Accessibility* — do not encode financial meaning by hue alone in Phase 1 tables.

---

## 3. Upload and validation UX

### Decision: **Preview first 5 rows** before commit

**Why:** Users catch wrong sheet, wrong column order, or obvious format errors **before** server round-trip; reduces failed jobs and support load.

**UX principle:** *Error prevention* (Nielsen #5).

**Alternatives considered**

- **Upload immediately with no preview:** Rejected — higher failure rate; worse for large files.

### Decision: **Fail entire file** messaging is explicit and prominent

**Why:** Locked product rule — UI must never imply partial success when **zero rows** committed.

**UX principle:** *Match system truth to user mental model* (aligns with NFR “no silent failure”).

**Alternatives considered**

- **Partial success UI:** Out of scope — would contradict Phase 1 lock.

### Decision: **409 overlap** handled with **Replace** path + confirmation, not silent overwrite

**Why:** Approved decision — default **reject** overlap; **Replace** is destructive and must be **explicit** (checkbox + confirm modal).

**UX principle:** *Confirm destructive actions*; *forgiveness* with clear recovery path (adjust Replace + re-upload).

---

## 4. Progress and async jobs

### Decision: **Stepper + batch id** for ingestion; polling UI for **202 Accepted**

**Why:** API exposes async for large files; users need **traceability** (batch id) for Finance audit and support.

**UX principle:** *Visibility of system status* (Nielsen #1).

**Alternatives considered**

- **Spinner only:** Rejected — insufficient for long jobs; increases anxiety.
- **Email notification:** Deferred — not in Phase 1 PRD; optional later.

---

## 5. Data table and reconciliation

### Decision: **Tabular numerals** and **decimal-safe display** for amounts

**Why:** NFR requires **NUMERIC** semantics; UI must not suggest float rounding (avoid variable decimal jitter).

**UX principle:** *Recognition over recall* — amounts line up vertically for scanning.

### Decision: Show **batch_id** and **source_system** in Revenue table

**Why:** Traceability to import batch is a Finance persona need; supports spot-checks against Story 1.3.

**Alternatives considered**

- **Hide technical IDs:** Rejected for pilot Finance users — batch id is an audit anchor.

### Decision: **Uploaded by** on success summary and batch history (when API supports)

**Why:** PRD Finance persona needs **who loaded what, when**; `GET /ingest/batches/{batch_id}` includes `initiated_by`. Display **email or display name** resolved from that id when the backend exposes user resolution (or embed display fields in batch API). If Phase 1 ships without resolution, **omit the row** rather than show raw UUIDs to end users.

**Alternatives considered**

- **Always show raw UUID for initiator:** Rejected — not Finance-friendly.

### Decision: **Reconciliation strip** copy (user-facing)

**Why:** Spot-check path for Story 1.3 must not expose internal endpoint names. Use plain language: amounts match what is stored for the **current filters**, plus **page subtotal** labeling when the API does not return a full-result aggregate.

### Decision: **Export CSV** (Phase 1 optional)

**Why:** Personas reference exports for reconciliation; Phase 1 does **not** require a full analytics export. **Optional** toolbar action on **Revenue** exports the **same rows** as the current `GET /revenue` response for active filters (pagination rules: either export **current page only** or **all pages**—Tech Lead must pick one and label the button clearly, e.g. “Export this page” vs “Export all matching rows” if backend supports a dedicated export endpoint).

**If not built in Phase 1:** Document explicitly in release notes; Finance uses on-screen columns + batch id for pilot reconciliation.

### Decision: **Registration** UX scope

**Why:** `POST /auth/register` may be disabled in production. **Default Phase 1 pilot:** **Login only**; no self-service sign-up unless deployment enables it.

---

## 6. Responsive scope

### Decision: **Desktop-first**; **tablet** usable for review and upload; **phone** not a Phase 1 target

**Why:** Spreadsheet workflows and wide tables are impractical on small phones; effort better spent on correctness and validation UX.

**UX principle:** *Appropriate constraints* — optimize for actual enterprise usage (laptop + monitor).

**Alternatives considered**

- **Mobile-first tables:** Rejected for Phase 1 — high cost, low value for locked scope.

---

## 7. Icons

### Decision: **lucide-react** exclusively

**Why:** One coherent stroke set; aligns with common React stacks; tree-shakeable.

**UX principle:** *Consistency*.

**Alternatives considered**

- **Heroicons / Material:** Rejected to avoid mixed metaphors and bundle duplication.

---

## Decisions requiring **Product Owner approval** before Tech Lead build

These items are **not** blocked by engineering feasibility but by **product, compliance, or copy** ownership. Tech Lead should not implement conflicting behavior until resolved.

| # | Topic | What needs approval | Default UX assumption if silent |
|---|--------|---------------------|----------------------------------|
| 1 | **Default post-login route** | Confirm: **Import** vs **Revenue** vs **user preference** for users who already have data. | Import when zero batches; else last route or Revenue. |
| 2 | **Replace flow copy** | Exact **legal/Finance** wording for destructive replace (transactional delete + insert). | Technical but plain-language confirm modal as in `user-flows.md`. |
| 3 | **Download error report (CSV)** | Approve as Phase 1 must-have vs nice-to-have; affects Import error region. | List-only in Phase 1 if not approved. |
| 4 | **Template / column guide** | Whether PO supplies **official Excel template** URL or in-app spec; drives empty state secondary CTA. | Link placeholder until URL exists. |
| 5 | **Navigate away during async import** | Allow background processing with toast vs force stay on page. | Stay on Import with polling (safer MVP). |
| 6 | **Role names who may upload** | Which roles see enabled upload (`finance`, `admin`, `it_admin`) in pilot; drives disabled states. | Match `api-contracts.md` roles; disable with tooltip for others. |
| 7 | **Branding** | Product display name and logo asset for shell. | “Revenue Intelligence” text-only. |
| 8 | **Sum / subtotal row** | **Resolved in UX spec:** show **“Subtotal (this page only)”** when no full-scope aggregate exists; footnote that narrowing filters or export (if enabled) supports full extract. | As documented in `component-specs.md` / `user-flows.md`. |
| 9 | **Forgot password** | In scope for Phase 1 login or deferred. | Login error only; no link if deferred. |
| 10 | **Export CSV semantics** | If implemented, PO must confirm **one** behavior: export **current page** vs **all matching rows** (may need API). | Label button to match behavior; see §5 Data table / export decision above. |

---

## Traceability to principles (summary)

| Principle | Where applied |
|-----------|----------------|
| Nielsen: Visibility of status | Progress tracker, async batch id |
| Nielsen: Match real world | Finance-friendly errors, spreadsheet preview |
| Nielsen: Error prevention | Preview, Replace confirmation |
| Nielsen: Error recovery | Error list, 409 path, re-upload |
| Accessibility | Focus rings, reduced motion, no color-only money meaning |
| Trust (financial) | Tabular amounts, batch traceability, honest failure |

---

*End of document.*
