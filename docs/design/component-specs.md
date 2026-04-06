# Component Specifications — Phase 1 UI + Phase [1+1] (Phase 2) + Phase 3 + Phase 4 + Phase 5 + Phase 6 extensions

| Field | Value |
|--------|--------|
| **Status** | Phase 1 sections **Approved (PO)** — 2026-04-03; Phase [1+1] block **Draft — pending PO review** (new patterns flagged inline); **Phase 3 block Draft — pending PO review** (new patterns flagged inline); **Phase 4 block Draft — pending PO review** (new patterns flagged inline); **Phase 5 block Draft — pending PO review** (new patterns flagged inline); **Phase 6 block Draft — pending PO review** (new patterns flagged inline) |
| **Stack note** | React UI; icons from **lucide-react** per design system |
| **Aligned to** | `docs/requirements/product-requirements.md`, `docs/requirements/phase-2-requirements.md` (Phase [1+1]), **`docs/requirements/phase-3-requirements.md`**, **`docs/requirements/phase-4-requirements.md`**, **`docs/requirements/phase-5-requirements.md`**, **`docs/requirements/phase-6-requirements.md`**, `docs/architecture/api-contracts.md`, `docs/architecture/phase-2-changes.md`, `docs/architecture/phase-3-changes.md` |
| **Revision** | 2026-04-03 — Import batch history component, initiator on success card, Revenue icon, optional export. **2026-04-03 (b)** — Phase [1+1] analytics UI specs appended. **2026-04-06** — Phase 3 NL query + audit UI specs appended (per locked Phase 3 requirements). **2026-04-06 (b)** — Phase 4 HubSpot integration + reconciliation UI specs appended (per Phase 4 requirements draft). **2026-04-06 (c)** — Phase 5 enterprise intelligence UI specs appended (per locked Phase 5 requirements). **2026-04-06 (d)** — Phase 6 enterprise SSO, audit export, governance admin, and operational health UI specs appended (per locked Phase 6 requirements). |

---

## Phase [1+1] — New vs reused (summary)

Requirements source: [`phase-2-requirements.md`](../requirements/phase-2-requirements.md) (Stories **2.1–2.4**). Phase 1 specs in **§1–8** below remain the baseline; Phase [1+1] **adds** the following.

| Feature (story) | New screens / components | Reuses Phase 1 |
|-----------------|----------------------------|----------------|
| **2.1** Hierarchy aggregates | **Analytics** primary route (or agreed nav); **`HierarchyRollupTable`**; **`AnalyticsFilterToolbar`**; optional **`AccessScopeIndicator`** | `AppSidebar` pattern (§1); buttons, inputs, table density, money/UUID rules (design system §8–9); same card/surface tokens |
| **2.2** Period-over-period | **`PeriodComparisonPanel`** (comparison type + explicit periods + delta columns + missing-data states) | Date range patterns (design system §8.5); `text-body` / tabular numerals for deltas; select/button variants |
| **2.3** Filters & drill-down | **`ReconciliationStrip`** (or inline banner) when linking summary ↔ detail; drill affordances on rollup rows | **`RevenueFactsTable`** (§8) for detail; filter control styling from Import/Revenue toolbars |
| **2.4** Freshness / performance | **`AnalyticsFreshnessBanner`**; optional **`AnalyticsQueryProgress`** for long-running queries | `Loader2`, `AlertTriangle`, surfaces (`warning` / `success-muted`) per design system; progress timing tokens §7 |

**Does not require new product components:** Phase [1+1] **Import** flow (§2–7 placement) — unchanged unless PO later ties ingest messaging to analytics refresh in-app.

---

## 1. Navigation sidebar

### Component name

`AppSidebar` (or equivalent)

### Purpose

Persistent primary navigation and orientation within Phase 1 (Import, Revenue; future phases add items without redesigning shell).

### Layout description

- **Desktop:** Fixed **240px** width (token from design system), full viewport height below top bar (if global header exists) or flush top. Logo + product name at top; **nav items** as vertical list with icons + labels; user/tenant section at bottom.
- **Tablet:** Collapsible to **icon rail** (e.g. 64px) with tooltips; expand on tap for temporary overlay **or** hamburger that slides drawer—pick one pattern and stay consistent (see `ux-decisions.md`).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | One item **active** (filled/neutral background); others muted text. |
| **Hover** (inactive items) | Subtle background highlight; cursor pointer. |
| **Active** | Left border accent or background per design system; bold label optional. |
| **Focus** (keyboard) | Visible focus ring on nav links. |
| **Loading** | Rare; if tenant menu loading, skeleton in footer area. |
| **Error** | Optional toast if preferences fail—not typical for sidebar. |
| **Success** | N/A |
| **Empty** | N/A |
| **Disabled** | Item grayed; used if route exists but user lacks role (with tooltip “No access”). |

### Content

- **Text:** Nav labels — “Import”, “Revenue” (exact copy PO-approved).
- **Icons (lucide):** `Upload` or `FileSpreadsheet` for Import; **`Table`** for Revenue (read-only facts—do **not** use chart icons in Phase 1 to avoid implying Phase 2 analytics).
- **Data:** Current tenant name; user email or name in footer; optional environment badge (e.g. “Staging”) for dev.

### Interaction

| Action | Result |
|--------|--------|
| Click nav item | Client-side route change; active state updates. |
| Hover | Highlight inactive items. |
| Keyboard | Tab through links; Enter activates. |
| Escape (drawer mode) | Closes overlay on tablet. |

### Responsive behaviour

| Breakpoint | Behaviour |
|------------|------------|
| Desktop (≥1024px) | Full labels + icons. |
| Tablet (768–1023px) | Collapsed rail or drawer per decision doc. |

---

## 2. Upload drop zone

### Component name

`ExcelDropZone`

### Purpose

Receive `.xlsx`/`.xls` via drag-drop or file picker; communicate constraints and errors before upload starts.

### Layout description

- Dashed border region, min-height **160px**, centered icon + headline + short subtext + **Browse files** button.
- Placed **below** org/period/replace controls so users configure context first (recommended order).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Dashed border, neutral surface, icon `FileUp` or `Upload`. |
| **Hover** | Stronger border color; background tint. |
| **Drag over** | Accent border; “Drop file to upload” copy. |
| **Loading** | Overlay spinner; “Reading file…” if parsing for preview. |
| **Error** | Border error color; inline message (wrong type, too large). |
| **Success** | Brief checkmark after valid selection—then transitions to **File preview table** region. |
| **Empty** | Same as default—no file selected. |
| **Disabled** | Reduced opacity; no drag; tooltip “Select an organization first” or permission message. |

### Content

- **Text:** “Drag and drop your Excel file, or browse”; helper “.xlsx and .xls · max size per deployment”.
- **Icons:** `Upload`, `FileSpreadsheet`; error state `AlertCircle`.

### Interaction

| Action | Result |
|--------|--------|
| Click zone / Browse | Opens OS file picker filtered to Excel MIME/types. |
| Drop file | Validates extension/size; on pass, emits file to parent. |
| Keyboard | Focusable; Enter/Space opens picker when enabled. |

### Responsive behaviour

- **Desktop / tablet:** Full width in content column; touch-friendly hit area ≥44px for Browse.

---

## 3. File preview table

### Component name

`FilePreviewTable`

### Purpose

Show **first 5 data rows** (plus header row) so the user confirms the correct sheet/structure before committing to import.

### Layout description

- Card or bordered section; title **“Preview (first 5 rows)”**.
- HTML **table** or responsive scroll container on small widths; horizontal scroll if many columns.
- Footer line: file name, approximate row count if available.

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Populated columns from parsed file. |
| **Hover** | Row hover optional for readability (zebra striping per design system). |
| **Loading** | Skeleton rows (5) or spinner in table body. |
| **Error** | “Could not read this file” + message; link to try another file. |
| **Success** | N/A (preview is pre-success). |
| **Empty** | Hidden until file selected; if file has no rows, “No data rows found.” |
| **Disabled** | N/A |

### Content

- **Data:** Column headers from Excel row 1 (or detected header row); cells as plain text; **amount** columns use tabular alignment.
- **Icons:** None inside grid; optional `Info` tooltip on column explaining mapping to schema (Phase 1 optional).

### Interaction

| Action | Result |
|--------|--------|
| Horizontal scroll | Reveals overflow columns on narrow viewports. |
| Keyboard | Table is read-only; focusable scroll container. |

### Responsive behaviour

- **Desktop:** Full table.
- **Tablet:** Horizontal scroll; consider sticky first column if many fields (PO tradeoff).

---

## 4. Ingestion progress tracker

### Component name

`IngestionProgressTracker`

### Purpose

Communicate **upload → validate → commit** (or API-equivalent) progress and distinguish **sync** vs **async** processing.

### Layout description

- Horizontal **stepper** or vertical list of 3 steps: **Upload** · **Validate** · **Commit**.
- Optional linear progress bar under steps for indeterminate or determinate progress.
- For **202 Accepted**: show **batch_id** with **Copy** button and status “Processing…”.

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Idle/hidden until import starts **or** collapsed “Last import: …” |
| **Hover** | N/A (non-interactive except copy). |
| **Loading** | Current step emphasized; spinner on active step; previous steps checkmarked when done. |
| **Error** | Failed step marked with `XCircle`; summary line links to **Error list**. |
| **Success** | All steps checkmarked; transitions to **Success summary card** (may replace tracker prominence). |
| **Empty** | Hidden. |
| **Disabled** | Hidden when no job running. |

### Content

- **Text:** Step labels; async: “Processing in background (up to 30 minutes per job policy).”
- **Icons:** `CheckCircle2` (done), `Loader2` (spin), `XCircle` (fail)—lucide.

### Interaction

| Action | Result |
|--------|--------|
| Click Copy (batch id) | Copies UUID to clipboard; toast “Copied”. |
| Keyboard | Copy button focusable. |

### Responsive behaviour

- **Tablet:** Stack steps vertically if horizontal cramped.

---

## 5. Error list (row-level validation)

### Component name

`ImportErrorList`

### Purpose

Present **actionable** validation failures for a **rejected** file (entire file failed); never raw stack traces.

### Layout description

- **Alert** banner: **“Import failed — no data was loaded.”**
- Scrollable list (max-height e.g. **320px**) or paginated if >50 errors.
- Columns: **Row** · **Column/field** · **Message** (optional **Suggested fix** if message is long).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Visible when `status === failed` and errors exist. |
| **Hover** | Row hover for readability. |
| **Loading** | Skeleton lines while fetching batch detail (if errors loaded async). |
| **Error** | If error payload fails: inline “Could not load error details.” |
| **Success** | N/A — component hidden on success path. |
| **Empty** | If failed but no structured errors: generic message “Validation failed. Contact support with batch id.” |
| **Disabled** | N/A |

### Content

- **Data:** From API `error_log.errors[]`: `row`, `column`, `message`.
- **Icons:** `AlertTriangle` in banner; optional `Download` if CSV export added.

### Interaction

| Action | Result |
|--------|--------|
| Scroll | Navigate long lists. |
| Optional Export | Downloads CSV (if implemented). |

### Responsive behaviour

- **Tablet:** Table becomes stacked cards per row (row number + column + message).

---

## 6. Success summary card

### Component name

`ImportSuccessSummary`

### Purpose

Confirm **what** was loaded and **when**, with key audit fields for Finance (batch id, period, row counts).

### Layout description

- Elevated **card** (shadow level 1) with success border or icon header.
- Grid of key-value rows: **Batch ID**, **File name**, **Rows loaded**, **Period**, **Completed at** (local timezone label), **Uploaded by** (email or display name from resolved `initiated_by` when the API provides it—omit row if not available).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Full summary after success. |
| **Hover** | Card subtle lift optional (interactive card). |
| **Loading** | Skeleton card while polling async job to completion. |
| **Error** | N/A — use error list instead. |
| **Success** | Check icon + “Import complete”. |
| **Empty** | Hidden. |
| **Disabled** | N/A |

### Content

- **Text:** Success headline; optional “Next: Review revenue for this period.”
- **Data:** Maps from API: `batch_id`, `total_rows`, `loaded_rows`, `period_start`, `period_end`, filename from client or batch GET; **Uploaded by** from `initiated_by` + user lookup when implemented.
- **Icons:** `CheckCircle2`, `Copy` for batch id.

### Interaction

| Action | Result |
|--------|--------|
| Click **View revenue** | Navigates to Revenue with filters (batch or dates) applied. |
| Click Copy on batch id | Clipboard + toast. |

### Responsive behaviour

- **Tablet:** Key-value pairs stack full width.

---

## 7. Import batch history

### Component name

`ImportBatchHistory` (or `ImportBatchHistoryTable`)

### Purpose

Surface **recent import batches** for Finance traceability (“what was loaded, when”) and quick navigation to batch detail or filtered revenue. Backed by `GET /ingest/batches` (and optional drill-down to `GET /ingest/batches/{batch_id}`).

### Layout description

- Section title: **“Recent imports”** (or **“Import history”**).
- Table: **Status** · **File name** · **Completed** (or started) · **Rows loaded** / total · **Batch ID** (truncate + copy) · optional **Uploaded by** when API supports it.
- Rows link to batch detail route or expand inline for `error_log` on failed batches.
- Placed **below** the upload + terminal result area on the **Import** page so it stays visible during new uploads.

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Populated rows from latest batches (sorted newest first; limit e.g. 10–20). |
| **Hover** | Row hover; clickable row has pointer. |
| **Loading** | Skeleton rows. |
| **Error** | Inline alert + **Retry** (failed to load history). |
| **Success** | N/A |
| **Empty** | “No imports yet” with short line pointing to upload above. |
| **Disabled** | N/A |

### Content

- **Data:** From batch list items: `batch_id`, `filename`, `status`, `total_rows`, `loaded_rows`, `error_rows`, `started_at`, `completed_at`.
- **Icons:** `History` or `Inbox` for section; status badges use `CheckCircle2` (completed), `Loader2` (pending), `XCircle` (failed).

### Interaction

| Action | Result |
|--------|--------|
| Click row | Navigate to batch detail **or** open drawer with batch metadata and link **View in Revenue** (filter by `batch_id`). |
| Copy batch id | Clipboard + toast. |
| Keyboard | Rows focusable when interactive. |

### Responsive behaviour

- **Tablet:** Horizontal scroll or stacked cards per batch row.

---

## 8. Data table (view imported records)

### Component name

`RevenueFactsTable`

### Purpose

Read-only display of `GET /revenue` facts with filters and pagination.

### Layout description

- Toolbar: **filters** (org dropdown, optional BU/division, date range, optional batch id), **Apply** / auto-apply on change; optional **Export CSV** (Phase 1 **optional**—see `ux-decisions.md`; exports current result set returned for the active filters, not a separate analytics engine).
- **Reconciliation strip** (below toolbar or above table): row count for current page, **page subtotal** of amounts with label **“Subtotal (this page only)”** unless API provides full-scope aggregate.
- Table: columns — **Revenue date** · **Amount** · **Currency** · **Org** · **BU** · **Division** · **Customer** · **Revenue type** · **Source** · **Batch ID** (truncate + copy).
- Footer: pagination **Previous** / **Next** + “Showing X–Y” using `limit`; opaque `cursor` hidden from user.

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Populated rows or empty state inside table body. |
| **Hover** | Row hover; sortable column headers show sort icon on hover if sorting enabled. |
| **Loading** | Skeleton rows. |
| **Error** | Inline alert above table + Retry. |
| **Success** | N/A |
| **Empty** | Single row illustration: “No data for current filters.” |
| **Disabled** | Filters disabled while loading. |

### Content

- **Amount:** Display decimal strings with thousands separators; **tabular figures**; right-align.
- **IDs:** Short UUID or monospace full with copy; hierarchy names when API enriches (Phase 1 may show IDs—copy-friendly).

### Interaction

| Action | Result |
|--------|--------|
| Change filter | Refetch revenue list. |
| Pagination | Request next page with `cursor`. |
| Export CSV (if enabled) | Downloads CSV for rows in current response (same scope as on-screen results). |
| Click batch id | Copy or filter-by-batch (PO preference). |
| Keyboard | Tab through interactive cells; Enter on buttons. |

### Responsive behaviour

- **Desktop:** Full table.
- **Tablet:** Horizontal scroll; sticky first column (date) recommended.

---

## Cross-component placement (Phase 1 Import page)

Suggested vertical order:

1. Page title + short description  
2. Form: Organization → Period → Replace checkbox  
3. **ExcelDropZone**  
4. **FilePreviewTable** (when file selected)  
5. Primary button: **Start import**  
6. **IngestionProgressTracker** (when running)  
7. **ImportSuccessSummary** **or** **ImportErrorList** (terminal state)  
8. **ImportBatchHistory** (always visible; empty state until first batch)

---

**Phase [1+1] (Phase 2) — sections 9–17.** The following specs **extend** the Phase 1 design system (`docs/design/design-system.md`). **No new visual tokens** are introduced unless called out with **⏸ PO approval** (new pattern).

## 9. Analytics page shell (hierarchy rollup)

### Component name

`AnalyticsPage` (route-level view; name implementation-flexible)

### Purpose

Host **Story 2.1** — hierarchical revenue totals for a chosen **rollup level** and **time scope**, backed by `GET /api/v1/analytics/revenue/rollup` (see `phase-2-changes.md`).

### Layout description

- **Page title** (`text-display`): e.g. **“Revenue analytics”** (exact copy **⏸ PO approval**).
- Short supporting line (`text-small`, `text-secondary`): one sentence on rollup scope (align with PRD CXO/BU Head clarity).
- Vertical stack: optional **`AccessScopeIndicator`** → **`AnalyticsFreshnessBanner`** → **`AnalyticsFilterToolbar`** → **`HierarchyRollupTable`** → optional **`ReconciliationStrip`** when a row is selected for drill-down preview.
- **Horizontal padding / section gaps:** per design system §3 (`space-6` page padding desktop).

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Toolbar + table populated or empty state. |
| **Loading** | Skeleton for table rows; toolbar fields disabled where appropriate. |
| **Error** | Inline alert (`error` / `error-surface`) + **Retry** primary pattern (§8.2). |
| **Empty** | “No data for current filters.” — same tone as `RevenueFactsTable` empty (§8). |

### Content

- **Icons:** Section may use `LayoutGrid` or `BarChart3` for nav (see §1 extension); **no chart graphics** in this spec unless **⏸ PO approval** adds chart library / sparklines.

### Interaction

| Action | Result |
|--------|--------|
| Change filters / rollup level | Refetch rollup API; preserve explicit period labels in UI. |
| Activate drill-down | Navigate or deep-link to Revenue detail with matching filters (Story 2.3). |

### Responsive behaviour

- **Tablet:** Toolbar stacks; table horizontal scroll with sticky first column (hierarchy label) recommended — same pattern as §8.

### ⏸ PO approval — navigation placement

- **Option A:** New primary nav item **“Analytics”** alongside Import / Revenue.
- **Option B:** Tabs or nested route under **Revenue** (Facts vs Analytics).

Pick one in `ux-decisions.md`; implementation must not invent a third pattern without PO sign-off.

---

## 10. Hierarchy rollup table

### Component name

`HierarchyRollupTable`

### Purpose

Display **rolled-up revenue** by org hierarchy level (org / BU / division per API) with **child sums reconciling to parents** (Story 2.1 AC).

### Layout description

- Read-only **table**: columns at minimum — **Hierarchy** (node name or path), **Revenue** (amount + currency code), optional **Row count** / **% of parent** if API provides.
- **Indentation** or **grouped rows** to show parent/child; **no pie/donut charts** in baseline spec (tabular finance trust — design system §9).
- Row height **≥44px**; amounts right-aligned, tabular numerals, **neutral** text color for money (design system §1, §9).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Data rows from rollup API. |
| **Hover** | Row hover for readability; **clickable** rows if drill-down enabled (pointer). |
| **Loading** | Skeleton rows. |
| **Error** | Parent handles; or inline cell “—” with tooltip if partial. |
| **Empty** | Single message row (not illustrated chart). |

### Content

- **Data:** From `GET /analytics/revenue/rollup` response shapes per `api-contracts.md` (locked in implementation).
- **Icons:** Optional `ChevronRight` on drill affordance; status N/A inside grid.

### Interaction

| Action | Result |
|--------|--------|
| Click row (if drill enabled) | Opens detail path (Story 2.3) with filters applied; optional reconciliation strip updates. |
| Keyboard | Focusable rows when interactive; arrow navigation **⏸ PO approval** if custom grid (else native table focus). |

### Responsive behaviour

- Horizontal scroll; consider sticky hierarchy column.

### Reuses Phase 1

- Table density, zebra/striping, typography from **`RevenueFactsTable`** (§8) and design system §9.

---

## 11. Analytics filter toolbar

### Component name

`AnalyticsFilterToolbar`

### Purpose

Collect **AND-combined** filters (org, BU, division, revenue type, customer, time scope) for analytics queries; deterministic updates (Story 2.1, 2.3).

### Layout description

- Horizontal **toolbar** (wraps on narrow viewports): native `<select>` or accessible listbox for dimensions; **date range** or **period** controls per design system §8.5 (explicit `YYYY-MM-DD` labels).
- **Apply** button (primary) or debounced auto-apply — **⏸ PO approval** to match Revenue page behavior for consistency.
- Uses **40px** controls, `radius-sm`, spacing §3.

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Enabled selects. |
| **Loading** | Disabled controls + optional inline `Loader2` near Apply. |
| **Error** | Banner or field error for invalid range. |

### Content

- Labels: sentence case; **BU** / **Division** disabled or hidden when not applicable per API.

### Interaction

| Action | Result |
|--------|--------|
| Apply | Emits filter model to parent; triggers rollup (and comparison sub-panel if visible). |

### Responsive behaviour

- Stack fields vertically with `space-4` between rows on small screens.

### Reuses Phase 1

- Same control specs as Import org/period and Revenue toolbar (§8 Phase 1 placement).

---

## 12. Period comparison panel

### Component name

`PeriodComparisonPanel`

### Purpose

**Story 2.2** — choose **metric** (e.g. revenue), **comparison type** (MoM / QoQ / YoY as shipped), and **two explicit periods**; show **absolute** and **relative** change with **clear period labels**.

### Layout description

- **Sub-section** under or beside rollup (layout **⏸ PO approval**): controls row + results table or extra columns on rollup.
- **Required copy pattern:** “**A:** [period] · **B:** [period]” — never ambiguous “last quarter” without confirmation.
- Columns: **Period A amount**, **Period B amount**, **Δ amount**, **Δ %** (format per locale; **0 divide** and **missing leg** handled in content, not as fake zeros).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Comparison results or prompt to select periods. |
| **Loading** | Skeleton or disabled panel. |
| **Missing data** | **Warning** surface (`warning-surface` + `AlertTriangle`): “No data for period A” / “… for period B” — explicit, not zero revenue (AC). |

### Content

- **Icons:** `CalendarRange` near period pickers; `AlertTriangle` for missing leg.

### Interaction

| Action | Result |
|--------|--------|
| Change comparison type | Refetch `GET /api/v1/analytics/revenue/compare` (per contracts). |

### Reuses Phase 1

- Buttons, selects, alerts — design system §8; no new color roles.

### ⏸ PO approval

- **Fiscal vs calendar** labels if pilots need non-calendar quarters (follow-up in `phase-2-requirements.md`).

---

## 13. Reconciliation strip (summary ↔ detail)

### Component name

`ReconciliationStrip`

### Purpose

**Story 2.3** — when user moves from **rolled-up summary** to **`GET /revenue` detail**, show that the **detail set** matches the **summary total** for the same filters (or explain discrepancy if API reports block).

### Layout description

- **Thin banner** below toolbar or above detail table: `primary-muted` or `surface-subtle` background; `text-small`.
- Example copy pattern: “**Detail view** — subtotal **$X** for selected filters (matches analytics summary).” If mismatch: **warning** styling + short reason **per API contract** (not stack traces).

### Visual states

| State | Appearance |
|-------|------------|
| **Reconciled** | Neutral / success-muted icon `CheckCircle2` optional. |
| **Partial / stale** | `AlertTriangle` + link to **freshness** (§14). |

### Interaction

| Action | Result |
|--------|--------|
| Optional link | Scroll to **`AnalyticsFreshnessBanner`** or open docs tooltip. |

### Reuses Phase 1

- Banner spacing and typography consistent with **`ImportErrorList`** banner (§5) but informational tone, not failure.

---

## 14. Analytics freshness banner

### Component name

`AnalyticsFreshnessBanner`

### Purpose

**Story 2.4** — communicate **precomputed** data **freshness** (`GET /api/v1/analytics/freshness` / rollup `as_of`) so users are not misled after ingest or replace imports.

### Layout description

- **Non-blocking** strip at top of analytics (and optionally Revenue) view: `text-small`; “**Data as of:** [timestamp] ([timezone])” per design system date copy (§8.5).
- If stale vs last ingest: **warning** variant (`warning-surface`) with optional **Refresh** only if product adds client-triggered refresh (**⏸ PO + architect**).

### Visual states

| State | Appearance |
|-------|------------|
| **Fresh** | Muted info line; optional `CheckCircle2`. |
| **Stale / refreshing** | `Loader2` + “Updating aggregates…” if async refresh exposed. |

### Content

- No raw job IDs unless PO asks; align with observability personas in parent PRD.

### Reuses Phase 1

- Same surfaces and icons as ingestion copy patterns (`IngestionProgressTracker` §4).

---

## 15. Access scope indicator (BU row-level)

### Component name

`AccessScopeIndicator`

### Purpose

When **`GET /me`** includes **`business_unit_scope`** (Phase 2), show **which BUs** the user may see — required for trust under Story 2.1 AC (row-level access).

### Layout description

- **Inline** text or **badge** (`text-micro`, `radius-sm`): e.g. “**Showing:** Acme — Widgets BU” or “**Org-wide access**” when scope is empty/full.
- Placed **under page title** or **toolbar**; does not replace dimension filters.

### Visual states

| State | Appearance |
|-------|------------|
| **Scoped** | Neutral text; optional `Building2` 16px. |
| **Loading** | Skeleton text line. |

### Reuses Phase 1

- Badge scale from design system `text-micro`; **no** new colors.

---

## 16. Analytics query progress (optional)

### Component name

`AnalyticsQueryProgress`

### Purpose

If engineering uses **async** analytics queries (per `phase-2-requirements.md` AC), show **user-visible** progress instead of a silent hang.

### Layout description

- **Inline** `Loader2` + **“Loading analytics…”** or linear indeterminate bar under toolbar — duration tokens §7 (`duration-base`).

### Reuses Phase 1

- Same spinner and disabled-button pattern as **`IngestionProgressTracker`** (§4) but **single-line**; do **not** reuse three-step stepper unless PO extends spec.

### ⏸ PO approval

- Full-screen blocking modal vs inline — pick one for consistency with NFR “interactive” expectations.

---

## 17. AppSidebar — Phase [1+1] extension (delta to §1)

| Addition | Spec |
|----------|------|
| **New item** | Label **“Analytics”** (or PO-approved synonym); route to `AnalyticsPage` (§9). |
| **Icon (lucide)** | `BarChart3` **or** `LayoutGrid` — **⏸ PO approval** (Phase 1 deliberately avoided chart-implying icons on **Revenue**; Phase 2 explicitly delivers analytics). |
| **Order** | Import · Revenue · Analytics — **⏸ PO approval** if different. |

**Reuse:** All §1 behaviors (active, hover, focus, responsive) unchanged.

---

## Phase 3 — New vs reused (summary)

Requirements source: [`phase-3-requirements.md`](../requirements/phase-3-requirements.md) (Stories **3.1–3.4**). Phase 1 (§1–8) and Phase 2 (§9–17) remain the baseline. Phase 3 **adds** governed natural-language query UX and an **audit** surface for IT/Finance.

| Feature (story) | New screens / components | Reuses Phase 1–2 |
|-----------------|---------------------------|------------------|
| **3.1** Map business terms to semantic layer | **`NLQueryPage`** (shell); **`NLQueryComposer`**; **`ResolvedInterpretationPanel`** (or inline summary) showing canonical interpretation for trust | `AppSidebar` pattern (§1, §17); buttons, inputs (design system §8); **tabular result display** via same density/typography rules as `HierarchyRollupTable` / `RevenueFactsTable` (§10, §8); `Loader2` for LLM/execute waits (§4, §16) |
| **3.2** Validate before execute | **`NLQuerySafetyMessage`** (structured user-safe copy for blocked/timeout/limit paths — not raw traces) | Alert/banner patterns (`ImportErrorList` §5, `AnalyticsPage` error §9); `error` / `warning` surfaces (design system §1); optional **`AnalyticsFreshnessBanner`** (§14) if freshness must be cited in NL results |
| **3.3** Disambiguation | **`DisambiguationPanel`** (choices + submit/resume via same NL session) | `Checkbox` / radio / `select` (§8.3–8.4); primary **Submit** / secondary **Cancel** (§8.2); `AlertTriangle` for non-guess emphasis (design system §6) |
| **3.4** Query audit log | **`NLQueryAuditLogPage`**; **`NLQueryAuditTable`** (list + optional row expand / link to detail) | `RevenueFactsTable`-style read-only table scaffolding (§8): pagination affordance, monospace + Copy for ids, `text-small` metadata; role-gated access pattern consistent with §1 **Disabled** nav (no new auth UI pattern) |

**Does not require new product UI (baseline Phase 3):** **Synonym/metric maintenance** and **semantic layer versioning** are satisfied by **documented change control** and backend/repo artifacts unless PO adds an **admin** synonym editor — **⏸ PO approval** before designing maintainer screens.

**Follow-up (non-blocking) from Phase 3 doc — ⏸ PO approval before implementation:** dedicated page vs chat-style **panel** in existing shell; **mobile** vs desktop-first v1; **export** of NL results; **localization**. Architect-owned items (sync/async NL UX, timeouts) affect loading/progress copy only — reuse **`AnalyticsQueryProgress`** (§16) / inline `Loader2` patterns; **no new motion tokens**.

---

## 18. NL Query page (shell)

### Component name

`NLQueryPage` (route-level view; name implementation-flexible)

### Purpose

**Stories 3.1–3.3** — Primary place for business users to **submit** a natural-language revenue question, see **resolved interpretation** (trust), handle **disambiguation**, and view **results** that reconcile with Phase 2 analytics definitions for equivalent filters/periods.

### Layout description

- **Page title** (`text-display`): e.g. **“Ask revenue”** or **“Natural language query”** — exact copy **⏸ PO approval**.
- Short supporting line (`text-small`, `text-secondary`): one sentence on governed, read-only execution (align with Phase 3 goal sentence).
- Vertical stack: **`NLQueryComposer`** → optional **`DisambiguationPanel`** (when API returns clarification need) → **`ResolvedInterpretationPanel`** (when interpretation is available) → **`NLQueryResultPanel`** (tabular or summary per API) → **`NLQuerySafetyMessage`** on validation/scope failures.
- **Horizontal padding / section gaps:** design system §3 (`space-6` desktop).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Composer enabled; empty result region or placeholder. |
| **Loading** | Composer **disabled** or `aria-busy`; inline **`Loader2`** + “Interpreting…” / “Running query…” (`text-small`) — duration tokens §7. |
| **Needs clarification** | **`DisambiguationPanel`** visible; composer may remain for revised question **or** be replaced by choice UI only — **⏸ PO approval** (single consistent pattern). |
| **Error** | **`NLQuerySafetyMessage`** + **Retry** where applicable (primary §8.2); never raw stack traces. |
| **Feature off** | If `ENABLE_NL_QUERY` is false: empty state card (`surface-elevated`, `radius-md`) with short explanation and link to **Analytics** — **⏸ PO approval** for exact copy. |

### Content

- **Icons (lucide):** `MessageSquareText` or `Sparkles` for section accent — **⏸ PO approval** (avoid implying ungoverned chat); **`CalendarRange`**, **`Building2`** only inside interpretation/disambiguation content where relevant (design system §6).

### Interaction

| Action | Result |
|--------|--------|
| Submit question | `POST /query/natural-language` (per `phase-3-changes.md`); update thread state. |
| Complete disambiguation | Same contract with `disambiguation_token` + `clarifications` — no **silent** auto-submit without user confirmation. |

### Responsive behaviour

- **Tablet:** Stack panels; composer full width; result table horizontal scroll (same as §8, §10).

### ⏸ PO approval — shell pattern

- **Option A:** Dedicated **primary route** (new nav item — see §25).
- **Option B:** **Drawer / slide-over** from Analytics or global action — **not** in Phase 1–2 specs; **requires PO approval** as a new layout pattern.

---

## 19. NL Query composer

### Component name

`NLQueryComposer`

### Purpose

**Stories 3.1, 3.3** — Text entry for the user’s question; supports **submit** and accessible **busy** state during LLM/query work.

### Layout description

- **Multiline** text area (min-height ~96px) or single-line input expanding to multiline — **⏸ PO approval** (keep one pattern).
- **Primary** button **“Ask”** / **“Run query”** (copy **⏸ PO approval**); optional secondary **Clear**.
- Helper line (`text-small`, `text-secondary`): e.g. plain-language tips (no legal disclaimer block unless compliance asks).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Empty or draft text; border `color-border`, focus ring §8.1. |
| **Loading** | Button shows `Loader2` + shortened label; `aria-busy="true"`; inputs disabled if product requires single-flight. |
| **Error** | Field-level error only for client validation (empty submit); server errors use **`NLQuerySafetyMessage`**. |

### Content

- Placeholder example — **⏸ PO approval** (keep one short example aligned to pilot vocabulary).

### Interaction

| Action | Result |
|--------|--------|
| Submit | Validates non-empty; emits to parent for API call. |
| Keyboard | Enter may submit **⏸ PO approval** if multiline, prefer Ctrl+Enter to avoid accidental submit. |

### Reuses Phase 1

- Input height, padding, `radius-sm`, focus/error from design system **§8.1**; primary button **§8.2**.

---

## 20. Resolved interpretation panel

### Component name

`ResolvedInterpretationPanel`

### Purpose

**Story 3.1** — Show **what the system understood** (canonical metric, period, dimensions, comparison type) in **structured, scannable** form so users trust the answer and **no silent synonym drift** is perceived as magic.

### Layout description

- **Card** or bordered region (`surface-elevated`, `radius-md`, `shadow-sm`).
- Heading (`text-heading`): **“Interpretation”** or **“Resolved question”** — **⏸ PO approval**.
- Key-value list or bullet list (`text-body`): period labels explicit (**A/B** pattern consistent with **`PeriodComparisonPanel`** §12 where comparisons apply); BU/division names; metric name matching Finance vocabulary.

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Populated from API resolved plan summary. |
| **Loading** | Skeleton lines (`space-3` gap). |
| **Empty** | Hidden until first successful resolution. |

### Reuses Phase 2

- Explicit period labeling discipline from **`PeriodComparisonPanel`** (§12); hierarchy labels consistent with **`HierarchyRollupTable`** (§10).

---

## 21. NL Query result panel

### Component name

`NLQueryResultPanel`

### Purpose

**Stories 3.1–3.2** — Present **answer data** in UI form (table and/or summary numbers) such that numbers **reconcile** with **`GET /analytics/*`** and **`GET /revenue`** for the same logical filters (per requirements — implementation binds to shared services).

### Layout description

- Prefer **existing table/list patterns**: same **money** rules (neutral text, tabular numerals, currency code — design system §9).
- If the API returns a **rollup-shaped** result: reuse column semantics from **`HierarchyRollupTable`** (§10). If **fact-level** rows: align with **`RevenueFactsTable`** (§8).
- Optional **Reconciliation** line: if product shows “matches Analytics filter X” — reuse tone from **`ReconciliationStrip`** (§13) without new colors.

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Data rows or summary. |
| **Loading** | Skeleton rows (§7 skeleton pulse). |
| **Empty** | “No rows returned” — same tone as §8 empty state. |

### Reuses Phase 1–2

- **`RevenueFactsTable`** (§8), **`HierarchyRollupTable`** (§10), **`PeriodComparisonPanel`** (§12) as **visual and density references** — **no new chart graphics** unless **⏸ PO approval** (design system alignment).

---

## 22. Disambiguation panel

### Component name

`DisambiguationPanel`

### Purpose

**Story 3.3** — Present **explicit choices** (period, BU, metric, comparison type, etc.) when the model/API indicates ambiguity; **no silent guess** on financially material interpretation.

### Layout description

- **Card** (`surface-elevated`, `radius-md`) with heading (`text-heading`): **“Clarify your question”** — **⏸ PO approval**.
- For each clarification prompt from API: **radio group** or **select** (native or accessible listbox per §8.3) with `space-4` between prompts.
- **Primary** **Continue** / **Apply choices**; optional **Back** if multi-step — **⏸ PO approval** vs single screen.

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Awaiting user selection. |
| **Loading** | Primary button busy; form disabled. |
| **Error** | Inline `AlertTriangle` + short message if submission fails. |

### Content

- Choice labels: **sentence case**; show **canonical** names (e.g. fiscal quarter label) when API provides them.

### Interaction

| Action | Result |
|--------|--------|
| Submit | Calls `POST /query/natural-language` with `disambiguation_token` and structured `clarifications` (per architecture doc). |

### Reuses Phase 1

- Form controls §8; **`Checkbox`** §8.4 if multi-select clarifications are supported — **⏸ architect/PO** on multi vs single select per prompt type.

---

## 23. NL Query safety message

### Component name

`NLQuerySafetyMessage`

### Purpose

**Story 3.2** — User-appropriate messaging when execution is **blocked** (out-of-scope, non–read-only path rejected, row limit, timeout, rate limit, model unavailable). **Not** raw provider traces.

### Layout description

- **Inline alert** region: `error-surface` or `warning-surface` per severity (destructive rejection vs retryable limit).
- Icon: `AlertCircle` or `AlertTriangle` (lucide, 16–20px) + **headline** (`text-body-strong`) + **body** (`text-body`).
- **Retry** (secondary/primary per severity) when applicable; **no** technical sub-message unless PO approves “support reference id” line.

### Visual states

| State | Appearance |
|-------|------------|
| **Blocking** | `error` / `error-surface`. |
| **Retryable** | `warning` / `warning-surface`. |

### Reuses Phase 1

- Same structural pattern as **`ImportErrorList`** banner (§5) and **`AnalyticsPage`** error (§9); tokens from design system §1.

---

## 24. NL Query audit log page and table

### Component name

`NLQueryAuditLogPage`, `NLQueryAuditTable`

### Purpose

**Story 3.4** — Let **IT Admin** and **Finance** review **who** asked **what**, **when**, and **executed plan / query summary** (as returned by API), with **authenticated**, **role-appropriate** access.

### Layout description

- **Page title** (`text-display`): **“Query audit log”** — **⏸ PO approval**.
- Intro line (`text-small`, `text-secondary`): retention notice (e.g. **365 days** operational default per requirements) — exact legal copy **⏸ PO/compliance**.
- **`NLQueryAuditTable`**: columns at minimum — **When** (timestamp, local TZ label per §8.5) · **Who** (user id / email per API) · **Natural language asked** (truncated + expand) · **Plan / summary** (truncated + expand or link to **`GET /query/audit/{log_id}`** detail).
- **Append-only** presentation: **no** edit/delete affordances in UI (read-only table).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Rows from `GET /query/audit`. |
| **Loading** | Skeleton rows. |
| **Error** | Inline alert + **Retry** (§8.2). |
| **Empty** | “No audit entries in this range.” |
| **Forbidden** | If 403: use same user-safe message pattern as **`NLQuerySafetyMessage`** (§23); do not expose role names unnecessarily. |

### Content

- **PII / prompt display** follows compliance policy — redaction **⏸ architect**; UI shows whatever API exposes for authorized roles.

### Interaction

| Action | Result |
|--------|--------|
| Pagination / date filter | **⏸ PO approval** for filter toolbar scope (reuse toolbar density from **`AnalyticsFilterToolbar`** §11). |
| Row click | Navigate to detail route or expand inline — **⏸ PO approval**. |

### Reuses Phase 1–2

- Table density §9; UUID/id **`Copy`** pattern §8; filter control styling **`AnalyticsFilterToolbar`** (§11).

### ⏸ PO approval

- **Export CSV** of audit — not in Phase 3 baseline requirements; add only if follow-up decision #3 (export) includes audit.

---

## 25. AppSidebar — Phase 3 extension (delta to §1 / §17)

| Addition | Spec |
|----------|------|
| **New item** | Label **“Ask”** / **“NL query”** / **“Query”** — **⏸ PO approval**; route to `NLQueryPage` (§18). |
| **Icon (lucide)** | `MessageSquareText` **or** `Search` — **⏸ PO approval** (must not contradict governed/trust positioning). |
| **Order** | e.g. Import · Revenue · Analytics · Ask — **⏸ PO approval**. |
| **Gating** | If NL is disabled by flag, item hidden or disabled with tooltip — **⏸ PO approval**. |

**Reuse:** All §1 / §17 behaviors (active, hover, focus, responsive).

---

## Phase 4 — New vs reused (summary)

Requirements source: [`phase-4-requirements.md`](../requirements/phase-4-requirements.md) (Stories **4.1–4.3**). Phase 1–3 specs (§1–25) remain the baseline. Phase 4 **adds** governed **HubSpot** connection, **sync** visibility, **mapping exceptions**, and **Excel vs HubSpot reconciliation** UX—using existing tokens, table density, banners, and progress patterns from `docs/design/design-system.md` and prior sections.

| Feature (story) | New screens / components | Reuses Phase 1–3 |
|-----------------|---------------------------|------------------|
| **4.1** OAuth connection | **`HubSpotIntegrationPage`** (shell); **`HubSpotConnectionCard`** (connect CTA + health/status) | `AppSidebar` pattern (§1, §17, §25); primary/secondary buttons (design system §8.2); inline alerts (`error` / `warning` / success-muted surfaces — design system §1); status copy discipline similar to **`IngestionProgressTracker`** (§4) |
| **4.2** Incremental sync | **`HubSpotSyncStatusPanel`** (schedule summary, manual sync, in-progress / last-run outcome); **`HubSpotSyncHistoryTable`** (governance list of sync events) | **`IngestionProgressTracker`** (§4) step/spinner/copy patterns; **`AnalyticsQueryProgress`** (§16) for non-blocking async feedback; **`ImportBatchHistory`** (§7) table scaffolding (status, timestamps, row counts, retry); **`NLQueryAuditTable`** (§24) read-only append-only table tone |
| **4.3** Mapping + reconciliation | **`EntityMappingExceptionsTable`** (unmapped / ambiguous entities for resolution); **`SourceReconciliationView`** (compare HubSpot-sourced aggregates to Excel-sourced where both exist; surface conflicts—no silent overwrite narrative) | **`ImportErrorList`** (§5) actionable list + banner severity; **`RevenueFactsTable`** (§8) filters, money rules §9; **`PeriodComparisonPanel`** (§12) explicit period labels **A/B**; **`ReconciliationStrip`** (§13) summary↔detail trust copy; **`HierarchyRollupTable`** (§10) tabular aggregates; **`AnalyticsFilterToolbar`** (§11) filter density |

**Does not require net-new UI patterns (baseline Phase 4):** **Token storage, queues, idempotency, and rate limits** are backend/deployment concerns; UI only reflects **connection health**, **job outcomes**, and **documented partial-failure** messaging per requirements. **Full in-app exception workflow** (assign, comment, resolve) is **out of baseline** unless PO answers open question #5 in `phase-4-requirements.md` — **⏸ PO approval** before designing workflow beyond read-only exception lists and exports.

**⏸ PO approval — navigation / IA:** Dedicated **“Integrations”** or **“HubSpot”** primary nav item vs **Settings** sub-route vs **Admin**-only entry — same class of decision as Analytics (§9) and NL Query (§18); **do not** introduce a third shell pattern without PO sign-off.

---

## 26. HubSpot integration page (shell)

### Component name

`HubSpotIntegrationPage` (route-level view; name implementation-flexible)

### Purpose

**Story 4.1** — Host **OAuth connect**, **connection health** (connected / error / token refresh failed), and entry to **sync** and **mapping** subsections per IA decision.

### Layout description

- **Page title** (`text-display`): e.g. **“HubSpot”** or **“HubSpot integration”** — exact copy **⏸ PO approval**.
- Short supporting line (`text-small`, `text-secondary`): one sentence on governed ingestion and that Excel remains authoritative for booked actuals where the PRD applies (align with Phase 4 goal).
- Vertical stack: **`HubSpotConnectionCard`** → **`HubSpotSyncStatusPanel`** → **`HubSpotSyncHistoryTable`** (or tabs **Connection · Sync · History** — **⏸ PO approval** if tabs are new to product shell).
- **Horizontal padding / section gaps:** design system §3 (`space-6` desktop).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Cards populated or empty states per child components. |
| **Loading** | Skeleton cards; primary actions disabled where data is prerequisite. |
| **Error** | Inline alert + **Retry** (§8.2); never raw OAuth or provider traces. |

### Content

- **Icons (lucide):** `Plug` or `Link2` for integration context (design system §6 — no third-party logo assets in baseline spec unless PO provides brand kit); **`RefreshCw`** for sync; **`AlertCircle`** / **`AlertTriangle`** for unhealthy connection.

### Interaction

| Action | Result |
|--------|--------|
| Connect / disconnect | OAuth or API-driven flows per architecture — UI shows only user-safe outcomes. |

### Responsive behaviour

- **Tablet:** Stack cards full width; same as §9 / §18.

### Reuses Phase 1–3

- Page shell and error patterns from **`AnalyticsPage`** (§9), **`NLQueryPage`** (§18).

---

## 27. HubSpot connection card

### Component name

`HubSpotConnectionCard`

### Purpose

**Story 4.1** — **Primary** surface for **Connect to HubSpot** (or reconnect) and **persistent connection status** so operators are not blind to auth drift: at minimum **connected**, **error**, **token refresh failed** (or equivalent labels from API).

### Layout description

- **Card** (`surface-elevated`, `radius-md`, `shadow-sm`, internal padding `space-6`).
- **Status row:** `text-body-strong` label + **status badge** (`text-micro`, `radius-full` or `radius-sm`) using semantic colors: **success** / **error** / **warning** (token refresh failed — design system §1).
- **Primary** button: **Connect** / **Reconnect** (copy **⏸ PO approval**); **Secondary** **Disconnect** or **Manage in HubSpot** only if product ships those — **⏸ PO approval**.
- Optional **last verified** or **last successful token refresh** line (`text-small`, `text-secondary`) if API provides — **⏸ architect**.

### Visual states

| State | Appearance |
|-------|------------|
| **Connected** | Success-muted surface optional; badge “Connected” or PO-approved term. |
| **Error** | `error-surface` strip or border; `AlertCircle`; short user-safe message + **Retry** or **Reconnect**. |
| **Token refresh failed** | `warning-surface` + `AlertTriangle`; distinct from generic error if API distinguishes. |
| **Loading** | Primary button `Loader2` + `aria-busy`; card may skeleton status line. |

### Content

- No secrets or client IDs in UI; align with parent PRD Section 4 (Secrets).

### Interaction

| Action | Result |
|--------|--------|
| Connect | Starts OAuth redirect or modal per implementation; on return, refresh status from API. |

### Reuses Phase 1–3

- Button variants §8.2; badge scale `text-micro` (design system §2); alert structure like **`NLQuerySafetyMessage`** (§23) but for integration health.

### ⏸ PO approval

- **First-party OAuth consent screen** is external; in-app **empty state illustration** for never-connected tenants — only if PO wants parity with Import empty states (§7).

---

## 28. HubSpot sync status panel

### Component name

`HubSpotSyncStatusPanel`

### Purpose

**Story 4.2** — **Visible** outcomes for sync: **schedule** (or policy summary), **manual sync** trigger, **in-progress** feedback for async jobs, **last run** success/partial/failure summary, and **no silent success** when material rows failed validation (user-safe summary, not raw stack traces).

### Layout description

- **Card** or bordered region below connection card.
- Row 1: **Next / last scheduled sync** (`text-small`) — **⏸ PO approval** for how much schedule detail is shown (hourly vs daily vs manual-only).
- Row 2: **Primary** **Sync now** (or **Run sync**) with loading state; **disabled** when HubSpot not connected or job already running — tooltip from design system affordances.
- Row 3: **Last sync result** — timestamp (local TZ label per §8.5), counts (**processed / failed / skipped** if API provides), link to **history** or expand — **⏸ PO approval**.
- **Partial failure:** `warning-surface` banner + short explanation + link to **`HubSpotSyncHistoryTable`** detail — pattern aligned with **`ImportErrorList`** banner (§5) but informational/warning tone.

### Visual states

| State | Appearance |
|-------|------------|
| **Idle** | Last result visible or “No sync yet”. |
| **Running** | `Loader2` + “Sync in progress…” (`text-small`); **Sync now** disabled; optional linear indeterminate bar — reuse §7 duration tokens; **respect `prefers-reduced-motion`**. |
| **Succeeded** | `CheckCircle2` optional; neutral/success-muted text. |
| **Failed / partial** | `XCircle` / `AlertTriangle` per severity; explicit counts. |

### Content

- Long-running work must not block the shell without feedback (parent PRD NFR); if job is async, panel remains in **Running** until poll/webhook updates — same UX contract as **`IngestionProgressTracker`** async copy (§4).

### Interaction

| Action | Result |
|--------|--------|
| Sync now | Triggers job API; transitions to Running; on completion updates Last sync result. |

### Reuses Phase 1–3

- **`IngestionProgressTracker`** (§4), **`AnalyticsQueryProgress`** (§16), button loading §8.2.

---

## 29. HubSpot sync history table

### Component name

`HubSpotSyncHistoryTable`

### Purpose

**Stories 4.2, 4.3 (auditability)** — **Append-only** list of **sync events** (start, end, error summary) for IT/Finance governance; supports drill to row-level outcome without edit/delete affordances.

### Layout description

- Section title (`text-heading`): **“Sync history”** — **⏸ PO approval**.
- Table columns at minimum — **Started** · **Ended** (or duration) · **Status** · **Summary** (e.g. rows ingested, validation failures) · optional **Correlation id** (monospace + **Copy** per §8–9).
- Rows may link to **detail drawer** or route — **⏸ PO approval**.

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Newest-first rows. |
| **Loading** | Skeleton rows (§7). |
| **Error** | Inline alert + **Retry** loading history. |
| **Empty** | “No sync runs yet.” |

### Content

- Timestamps: local timezone label consistent with **`ImportSuccessSummary`** (§6) and **`NLQueryAuditTable`** (§24).

### Interaction

| Action | Result |
|--------|--------|
| Copy correlation id | Clipboard + toast (same as batch id patterns §4, §8). |

### Reuses Phase 1–3

- **`ImportBatchHistory`** (§7), **`NLQueryAuditTable`** (§24): density, badges, status icons (`CheckCircle2`, `Loader2`, `XCircle`).

### ⏸ PO approval

- **Export CSV** of sync history — not required in Phase 4 baseline doc; add if governance asks.

---

## 30. Entity mapping exceptions table

### Component name

`EntityMappingExceptionsTable`

### Purpose

**Story 4.3** — Surface **unmapped or ambiguous** HubSpot entities (e.g. company, deal, pipeline) as **exceptions for resolution**, not silent misclassification; read-only v1 unless PO approves workflow (see Phase 4 summary).

### Layout description

- Section title (`text-heading`): **“Mapping exceptions”** or **“Unresolved entities”** — **⏸ PO approval**.
- Toolbar (optional): filter by **exception type**, **pipeline**, **date range** — reuse **`AnalyticsFilterToolbar`** density (§11) with fewer fields.
- Table: **Entity type** · **HubSpot id / name** (PII display **⏸ PO** open question #6) · **Reason** (unmapped / ambiguous) · **Suggested action** (user-safe string from API) · **Updated** (timestamp).
- Banner when count > 0: `warning-surface` + `AlertTriangle`: short line that Finance/Admin should resolve before trusting rollups — tone similar to **`ReconciliationStrip`** (§13).

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Rows from exceptions API. |
| **Loading** | Skeleton rows. |
| **Error** | Inline alert + **Retry**. |
| **Empty** | “No mapping exceptions.” — optional `CheckCircle2` success-muted. |

### Interaction

| Action | Result |
|--------|--------|
| Row click | Navigate to resolution **or** expand — **⏸ PO approval**; baseline read-only list needs no click. |

### Reuses Phase 1–3

- **`ImportErrorList`** (§5) list semantics; **`RevenueFactsTable`** (§8) table scaffolding; UUID/copy rules §9.

---

## 31. Source reconciliation view

### Component name

`SourceReconciliationView` (section within a route or dedicated page — **⏸ PO approval**)

### Purpose

**Story 4.3** — Let Finance **compare** HubSpot-sourced aggregates to Excel-sourced **where both exist**; **surface conflicts** in a dedicated reconciliation / exception presentation (Excel authoritative for booked actuals; HubSpot does not silently overwrite—requirements).

### Layout description

- **Page or section title** (`text-display` or `text-heading`): **“Source reconciliation”** / **“Excel vs HubSpot”** — **⏸ PO approval**.
- Intro line (`text-small`, `text-secondary`): explains comparison grain (e.g. by customer, period, deal key — **exact labels ⏸ architect**).
- **Comparison grid** (tabular, no new chart library): columns at minimum — **Dimension** (e.g. customer / period) · **Excel total** · **HubSpot total** · **Delta** · **Conflict** (badge: None / Review — design system §1; **do not** rely on red/green alone for data direction — design system §1 Finance/trust rule).
- Optional **Reconciliation strip** above grid: reuse **`ReconciliationStrip`** (§13) wording pattern for “comparing sources for filters X”.
- **Conflicts** row or expandable detail: `warning-surface`, link to **`EntityMappingExceptionsTable`** when overlap is mapping-related.

### Visual states

| State | Appearance |
|-------|------------|
| **Default** | Data from reconciliation API. |
| **Loading** | Skeleton table. |
| **Error** | Inline alert + **Retry**. |
| **Empty** | “No overlapping data for current filters.” |
| **Missing one source** | **Warning** explicit leg (align **`PeriodComparisonPanel`** missing-data pattern — §12). |

### Content

- Money: tabular numerals, currency code, **neutral** text color for amounts (design system §9).

### Interaction

| Action | Result |
|--------|--------|
| Change filters | Refetch reconciliation — reuse filter control patterns **`AnalyticsFilterToolbar`** (§11). |
| Export | **⏸ PO approval** (open question #5 — read-only report/export may be v1 minimum). |

### Reuses Phase 1–3

- **`PeriodComparisonPanel`** (§12) for **explicit** period/source labels; **`HierarchyRollupTable`** (§10) for aggregate table density; **`ReconciliationStrip`** (§13).

### ⏸ PO approval

- **Dedicated primary nav** “Reconciliation” vs **tab under Revenue/Analytics** — IA decision; **no** third navigation invention without PO.

---

## 32. AppSidebar — Phase 4 extension (delta to §1 / §17 / §25)

| Addition | Spec |
|----------|------|
| **New item (optional)** | **“Integrations”**, **“HubSpot”**, or **Settings ▸ HubSpot** — **⏸ PO approval** (see § Phase 4 summary); route to **`HubSpotIntegrationPage`** (§26). |
| **Icon (lucide)** | `Plug` or `Link2` — consistent with §26; avoid CRM vendor glyph as product icon unless PO supplies assets. |
| **Order** | e.g. after **Import** or grouped with admin — **⏸ PO approval**. |
| **Gating** | IT Admin (or delegate) vs Finance — **⏸ PO** open question #1; nav item **disabled** with tooltip **“No access”** (§1) when role lacks connect permission. |

**Reuse:** All §1 / §17 / §25 behaviors (active, hover, focus, responsive).

---

## Phase 5 — New vs reused (summary)

Requirements source: [`phase-5-requirements.md`](../requirements/phase-5-requirements.md) (Stories **5.1–5.4**). Phase 1–4 specs (§1–32) remain the baseline. Phase 5 **adds** forward-looking and dimensional surfaces (**forecast**, **profitability / cost**, **customer segments**, **multi-currency**) that **compose** with existing actuals, source labeling, analytics, and NL—using established tokens, table density, banners, alerts, audit tables, and filter toolbars from `docs/design/design-system.md` and prior sections.

| Feature (story) | New screens / components | Reuses Phase 1–4 |
|-----------------|---------------------------|------------------|
| **5.1** Forecasting | **`ForecastingPage`** (shell); **`ForecastDisclaimerBanner`**; **`ActualsVsForecastPanel`** (explicit periods + separation); **`ForecastMethodologyPanel`**; **`ForecastSeriesTable`** (actual vs forecast rows + mode/version labels); optional **`ForecastVersionSelector`** | `AppSidebar` pattern (§1, §17, §25, §32); **`AnalyticsFilterToolbar`** (§11); **`PeriodComparisonPanel`** (§12) period-label discipline; **`HierarchyRollupTable`** (§10) / **`RevenueFactsTable`** (§8) tabular money rules §9; **`AnalyticsFreshnessBanner`** (§14) non-blocking strip pattern; **`ReconciliationStrip`** (§13) trust copy; banner severity tokens (`warning-surface`, `primary-muted` — design system §1); **`ImportSuccessSummary`** (§6) / batch id copy patterns for version identifiers |
| **5.2** Profitability | **`ProfitabilityPage`** (shell); **`ProfitabilityScopeBanner`** (what costs are included); **`MarginContributionTable`**; **`CostAllocationSummaryPanel`** (read-only basis / effective dates / traceability cues); **`ProfitabilityReconciliationStrip`** (link to revenue + cost lines) | Same table/toolbar/banner reuse as 5.1; **`SourceReconciliationView`** (§31) comparison-grid density and delta column semantics; **`EntityMappingExceptionsTable`** (§30) exception-list tone; **`ReconciliationStrip`** (§13); **`ImportErrorList`** (§5) actionable list structure (for reconciliation drill lists if needed) |
| **5.3** Segmentation | **`CustomerSegmentsPage`** (shell); **`SegmentDefinitionPanel`** (stored, replayable rules — form/list per architect); **`SegmentMembershipPreviewTable`**; **`SegmentDefinitionAuditTable`** (who/when/what for definition changes) | **`AccessScopeIndicator`** (§15) for org/BU scoping copy placement; **`AnalyticsFilterToolbar`** (§11); **`HierarchyRollupTable`** / **`RevenueFactsTable`** for segment-filtered results; **`DisambiguationPanel`** (§22) + **`ResolvedInterpretationPanel`** (§20) for NL segment alignment (Phase 3); **`NLQueryAuditTable`** (§24) append-only audit table scaffolding |
| **5.4** Multi-currency | **`TenantReportingCurrencyIndicator`** (inline or settings-adjacent); **`FxRateTable`** (pair, effective date, source label); **`FxRateUploadPanel`** (manual upload path per PRD); **`ConsolidatedMonetaryColumns`** pattern (reporting currency primary, native + FX metadata accessible — tooltip or expand row) | Money display rules §9 (currency code always visible); **`RevenueFactsTable`** (§8) column scaffolding; **`ImportBatchHistory`** (§7) / **`HubSpotSyncHistoryTable`** (§29) for upload-history table tone; **`ExcelDropZone`** (§2) + file validation patterns for rate file upload; **`FilePreviewTable`** (§3) optional preview before commit; monospace + **Copy** for rate batch ids if applicable |

**Does not require net-new visual tokens:** Phase 5 continues **tabular, finance-trust** presentation (design system §1 Finance/trust, §9). **Charts / sparklines** for forecast or profitability are **out of baseline** unless **⏸ PO approval** (same class of decision as §9 / §10 / §21).

**⏸ PO approval — IA / shell:** Single **“Forecasting”** / **“Profitability”** / **“Segments”** / **“Currencies”** (or **“FX”**) primary nav item vs **tabs under Analytics or Revenue** vs **Settings** sub-routes — pick one per area; **do not** invent a third navigation pattern without PO sign-off (align with §9, §18, §26).

**⏸ PO approval — new interaction patterns:** In-app **segment rule builder** complexity (visual builder vs form fields vs documented import-only) depends on architect item #5 in Phase 5 requirements; **full rule designer** is **not** specified as mandatory UI until PO/architect lock the rule language.

---

## 33. Forecasting page (shell)

### Component name

`ForecastingPage` (route-level view; name implementation-flexible)

### Purpose

**Story 5.1** — Host **forward-looking revenue** views with **non-misleading** separation from **actuals**, **prominent forecast disclaimer**, and **methodology** sufficient for Finance review (imported vs statistical mode, horizon, version).

### Layout description

- **Page title** (`text-display`): e.g. **“Forecasting”** or **“Revenue forecast”** — exact copy **⏸ PO approval**.
- Short supporting line (`text-small`, `text-secondary`): states that outputs are **informational** and **not** audited financial statements unless Finance exports/signs off outside the product (short pointer; full legal disclaimer may live in **`ForecastDisclaimerBanner`**).
- Vertical stack: **`ForecastDisclaimerBanner`** → optional **`TenantReportingCurrencyIndicator`** (§48) when multi-currency applies → **`AnalyticsFilterToolbar`**-density controls (§11) for org/BU/period/scenario → **`ActualsVsForecastPanel`** and/or **`ForecastSeriesTable`** → **`ForecastMethodologyPanel`** (collapsible **⏸ PO approval**).
- **Horizontal padding / section gaps:** design system §3 (`space-6` desktop).

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Child regions populated or empty per filters. |
| **Loading** | Skeleton for tables; toolbar disabled where appropriate. |
| **Error** | Inline alert (`error` / `error-surface`) + **Retry** (§8.2); user-safe copy only. |
| **Empty** | “No forecast data for current filters.” — tone consistent with §8 / §9 empty states. |

### Content

- **Icons (lucide):** `TrendingUp` or `LineChart` for section accent — **⏸ PO approval** (must not imply board-ready audited statements; prefer neutral `CalendarRange` + `Table` if PO rejects chart-implying icons).

### Interaction

| Action | Result |
|--------|--------|
| Change filters / scenario / version | Refetch forecast APIs; **no** silent mixing of actuals and forecast totals without explicit user-visible mode (AC). |

### Reuses Phase 1–4

- Page shell and error patterns from **`AnalyticsPage`** (§9), **`NLQueryPage`** (§18).

### ⏸ PO approval

- **Dedicated route vs tab** under Analytics — see Phase 5 summary IA note.

---

## 34. Forecast disclaimer banner

### Component name

`ForecastDisclaimerBanner`

### Purpose

**Story 5.1 AC** — **Prominent** UI disclaimer that forecast views are **not** audited financial statements unless Finance explicitly exports/signs off outside the product; supports trust without replacing legal/compliance review.

### Layout description

- **Full-width** or **inset** banner below page title: `warning-surface` or `primary-muted` (design system §1) — **⏸ PO approval** for severity (informational vs caution).
- `AlertTriangle` or `Info` (lucide, 16–20px) + **headline** (`text-body-strong`) + **body** (`text-body`, `text-secondary` for secondary sentences).
- Remains **visible** while user works on the page (not only on first visit) unless PO approves dismissible pattern — **⏸ PO approval**.

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Visible whenever `ForecastingPage` is shown. |
| **Collapsed** | **⏸ PO approval** — if dismissible, store preference per user/tenant. |

### Reuses Phase 1–4

- Banner structure and typography from **`ImportErrorList`** banner (§5) and **`NLQuerySafetyMessage`** (§23), with **informational** rather than failure tone.

---

## 35. Actuals vs forecast panel

### Component name

`ActualsVsForecastPanel`

### Purpose

**Story 5.1 AC** — Consolidated views that mix actuals and forecast use **explicit period boundaries**, **visual or textual separation**, and **no implication** that forecast equals actual.

### Layout description

- **Two-region** layout (stacked sections or side-by-side **⏸ PO approval**): **Region A — Actuals** and **Region B — Forecast** with **distinct** headings (`text-heading`) and repeated **period labels** (align **`PeriodComparisonPanel`** §12 explicit **A/B** labeling discipline).
- Optional **divider** (`border-strong`) or **spacing** (`space-8`) between regions — no single blended total row unless labeled **“Combined (informational)”** and PO approves — **⏸ PO approval**.
- **No** pie/donut or trend graphics in baseline; **tabular** subtotals per region preferred.

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Both regions populated or one empty with explicit “No actuals” / “No forecast” — not zero-filled ambiguity (align §12 missing-data pattern). |
| **Loading** | Skeleton blocks per region. |

### Reuses Phase 1–4

- **`PeriodComparisonPanel`** (§12) for explicit period legibility; **`HierarchyRollupTable`** (§10) density; design system §9 money neutrality.

### ⏸ PO approval

- **Visual “breakpoint” chart** between historical and forward periods — would be a **new chart pattern**; not in baseline spec.

---

## 36. Forecast methodology panel

### Component name

`ForecastMethodologyPanel`

### Purpose

**Story 5.1 AC** — **Transparency for Finance review:** inputs, horizon, revision/version if imported, model family if statistical — so the output is not an unexplainable black box.

### Layout description

- **Card** (`surface-elevated`, `radius-md`, `shadow-sm`, padding `space-6`).
- Key-value or definition list (`text-body`): **Source** (imported file vs statistical baseline), **Horizon**, **As-of / version** (per API), **Model** (if statistical), **Last updated** (timestamp + TZ per §8.5).
- Optional **link** to external sign-off or Finance workflow — **⏸ PO approval**.

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Populated from API. |
| **Loading** | Skeleton lines (`space-3`). |
| **Partial** | Show “Not available” for missing fields — **do not** fabricate methodology text. |

### Reuses Phase 1–4

- Card and KV layout from **`ResolvedInterpretationPanel`** (§20) and **`ImportSuccessSummary`** (§6).

---

## 37. Forecast series table

### Component name

`ForecastSeriesTable`

### Purpose

**Story 5.1** — Display **forecast amounts** (and adjacent **actuals** when in same view) with **clear labeling** of **which mode** produced a series (**imported** vs **statistical**) and **version** identifiers where applicable; **numeric** display per design system §9 and PRD Section 4.

### Layout description

- Read-only **table**: columns at minimum — **Period** (explicit labels) · **Series type** (Actual / Forecast badge) · **Mode** (Imported / Statistical — `text-micro` badges) · **Amount** · **Currency** · optional **Version** / **Scenario** (base / upside — **⏸ PO** open question #2).
- Row height **≥44px**; amounts right-aligned, tabular numerals, **neutral** text color for money (design system §1, §9).

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Data rows from API. |
| **Loading** | Skeleton rows (§7). |
| **Empty** | “No forecast series for current filters.” |

### Interaction

| Action | Result |
|--------|--------|
| Optional row expand | Show methodology snippet — **⏸ PO approval**. |

### Reuses Phase 1–4

- **`RevenueFactsTable`** (§8), **`HierarchyRollupTable`** (§10); badge scale `text-micro` (design system §2).

---

## 38. Forecast version selector (optional)

### Component name

`ForecastVersionSelector`

### Purpose

**Story 5.1 AC** — **Versioning / immutability:** UI control to choose **which published forecast version** or **effective-dated import** is displayed; changing underlying files must **not** silently overwrite prior versions without a **defined** strategy (backend binds; UI exposes choice).

### Layout description

- Native `<select>` or accessible listbox (§8.3): label (`text-body-strong`) + control (40px height, `radius-sm`).
- Helper (`text-small`, `text-secondary`): e.g. “Published versions only” — exact copy **⏸ PO approval**.

### Reuses Phase 1–4

- Same control specs as org/period pickers on Import and **`AnalyticsFilterToolbar`** (§11).

### ⏸ PO approval

- **Compare two versions** side-by-side — additional screen; not required in baseline spec.

---

## 39. Profitability page (shell)

### Component name

`ProfitabilityPage` (route-level view; name implementation-flexible)

### Purpose

**Story 5.2** — Host **margin or contribution** analysis with **explicit cost scope**, **traceability** to revenue and cost lines, and **same precision** presentation as revenue (design system §9).

### Layout description

- **Page title** (`text-display`): e.g. **“Profitability”** — **⏸ PO approval**.
- Vertical stack: **`ProfitabilityScopeBanner`** → filters (**`AnalyticsFilterToolbar`** §11 density) → **`MarginContributionTable`** → **`CostAllocationSummaryPanel`** → **`ProfitabilityReconciliationStrip`** → optional drill links to **`RevenueFactsTable`** (§8) / cost detail route — **⏸ PO approval**.

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Child components populated or empty. |
| **Loading** | Skeleton table. |
| **Error** | Inline alert + **Retry** (§8.2). |

### Reuses Phase 1–4

- **`AnalyticsPage`** (§9) shell patterns.

---

## 40. Profitability scope banner

### Component name

`ProfitabilityScopeBanner`

### Purpose

**Story 5.2 AC** — State **what costs are included** (e.g. COGS vs fully loaded) so narratives are not ambiguous; exact taxonomy is a **design/architect** decision.

### Layout description

- **Non-blocking** strip: `primary-muted` or `surface-subtle`; `text-small`.
- Single clear sentence + optional **“Learn more”** to **`CostAllocationSummaryPanel`** anchor — **⏸ PO approval**.

### Reuses Phase 1–4

- Tone and placement like **`ReconciliationStrip`** (§13) and **`AnalyticsFreshnessBanner`** (§14).

---

## 41. Margin and contribution table

### Component name

`MarginContributionTable`

### Purpose

**Story 5.2** — Display **revenue**, **cost**, **margin or contribution** at agreed grain with **NUMERIC**-grade display rules (formatting per locale; no float leakage in copy); reconciliation path to underlying lines (spot-check / export per PRD).

### Layout description

- Read-only table: columns **⏸ architect** (grain may be customer, BU, period) — at minimum **Revenue** · **Cost** · **Margin / contribution** · **Currency**; optional **% margin** with **divide-by-zero** handling explicit (align §12 zero/missing patterns).
- **No** red/green-only encoding for favorable/unfavorable variance — use labels, icons, or position (design system §1 Finance/trust).

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Data rows. |
| **Loading** | Skeleton rows. |
| **Empty** | “No profitability data for current filters.” |

### Reuses Phase 1–4

- **`HierarchyRollupTable`** (§10), **`SourceReconciliationView`** (§31) column semantics for deltas.

---

## 42. Cost allocation summary panel

### Component name

`CostAllocationSummaryPanel`

### Purpose

**Story 5.2 AC** — **Allocation rules remain explicit and traceable:** basis (e.g. revenue, headcount, driver), **effective dates**, and **who can change** (as documented); v1 UI is **read-only summary** unless PO extends maintainer workflow.

### Layout description

- **Card** (`surface-elevated`, `radius-md`, `shadow-sm`).
- Sections (`text-heading`): **Basis** · **Effective from / to** · **Owner / role** (if API provides) · **Audit** link to governance artifact — **⏸ PO approval**.
- If historical allocated results are versioned: short note + link — **⏸ architect**.

### Reuses Phase 1–4

- **`ResolvedInterpretationPanel`** (§20) KV structure; **`HubSpotConnectionCard`** (§27) card chrome.

### ⏸ PO approval

- **Editable allocation rules** in-product — new maintainer workflow; not baseline.

---

## 43. Profitability reconciliation strip

### Component name

`ProfitabilityReconciliationStrip`

### Purpose

**Story 5.2 AC** — Finance can **trace** displayed margin back to **underlying revenue and cost lines** for a defined scope; UI provides **explicit** copy and links (same trust posture as **`ReconciliationStrip`** §13).

### Layout description

- **Thin banner** below table or above detail: reuse **`ReconciliationStrip`** (§13) layout tokens; example pattern: “**Detail:** revenue subtotal **$X** · cost subtotal **$Y** for selected filters.”
- **Mismatch** or **partial scope:** `warning-surface` + short reason from API (not stack traces).

### Reuses Phase 1–4

- **`ReconciliationStrip`** (§13) verbatim pattern with profitability-specific labels.

---

## 44. Customer segments page (shell)

### Component name

`CustomerSegmentsPage` (route-level view; name implementation-flexible)

### Purpose

**Story 5.3** — Host **segment definitions**, **membership preview** (or results), **audit** of definition changes, and **access-scoped** filtering consistent with Phase 2 hierarchy rules.

### Layout description

- **Page title** (`text-display`): e.g. **“Customer segments”** — **⏸ PO approval**.
- Vertical stack: **`AccessScopeIndicator`** (§15) if BU scope applies → **`SegmentDefinitionPanel`** → **`SegmentMembershipPreviewTable`** → **`SegmentDefinitionAuditTable`**.
- Intro line (`text-small`): one sentence on **replayable** rules and **time behavior** (snapshot vs slowly changing — exact strings **⏸ architect/PO**).

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Panels populated or guided empty states. |
| **Loading** | Skeleton panels. |
| **Error** | Inline alert + **Retry**. |

### Reuses Phase 1–4

- **`AnalyticsPage`** (§9) shell; **`AccessScopeIndicator`** (§15).

---

## 45. Segment definition panel

### Component name

`SegmentDefinitionPanel`

### Purpose

**Story 5.3 AC** — **Segment definition rules** are **stored** and **replayable**; UI reflects **canonical** rule representation (no ad-hoc hidden filters). Exact control shape depends on architect **segmentation engine** decision.

### Layout description

- **Card** or form region: labeled fields **or** read-only rule summary from API — **⏸ PO + architect** (SQL-like vs UI builder vs import-only).
- **Primary** **Save** / **Publish** only if product ships in-app editing — **⏸ PO approval**; otherwise **read-only** with **“Change request”** external process — **⏸ PO approval**.
- **Materialization** indicator (`text-small`): “Membership as of [date]” — **⏸ architect**.

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Rule summary or editable fields. |
| **Loading** | Skeleton. |
| **Validation error** | Field-level + `AlertCircle` (§8.1). |

### Reuses Phase 1–4

- Form controls design system §8; **`DisambiguationPanel`** (§22) for structured choices if rules are picklists.

### ⏸ PO approval

- **Full visual rule builder** — may be a **new pattern**; defer until architect item #5 is locked.

---

## 46. Segment membership preview table

### Component name

`SegmentMembershipPreviewTable`

### Purpose

**Story 5.3** — Show **membership** for a selected segment definition and **as-of** context so **MoM/QoQ** comparisons are not misleading (time behavior explicit in copy above table).

### Layout description

- Read-only table: columns at minimum — **Customer** (or key) · **As-of** · optional **Attributes** (truncated) — **⏸ architect**.
- Respects **org/BU scoping** (§15); empty state explains **scope** vs **no members**.

### Reuses Phase 1–4

- **`RevenueFactsTable`** (§8) density and pagination affordances.

---

## 47. Segment definition audit table

### Component name

`SegmentDefinitionAuditTable`

### Purpose

**Story 5.3 AC** — **Audit:** material changes to segment definitions or **rule versions** are **traceable** (minimal viable: who / when / what changed).

### Layout description

- **`NLQueryAuditTable`**-style (§24): columns — **When** · **Who** · **Segment** · **Change summary** (truncated + expand); **append-only**; no delete/edit.

### Reuses Phase 1–4

- **`NLQueryAuditTable`** (§24), **`HubSpotSyncHistoryTable`** (§29).

---

## 48. Tenant reporting currency indicator

### Component name

`TenantReportingCurrencyIndicator`

### Purpose

**Story 5.4 AC** — **Single reporting currency per tenant** (default **USD** unless pilot contract specifies otherwise); always visible on **consolidated** views so users know which currency consolidation uses.

### Layout description

- **Inline** text or **badge** (`text-micro`, `radius-sm`): e.g. **“Reporting currency: USD”** — neutral text; placed under page title or in toolbar row (same placement discipline as **`AccessScopeIndicator`** §15).

### Reuses Phase 1–4

- **`AccessScopeIndicator`** (§15) layout; design system §9 currency labeling.

---

## 49. FX rate table and upload panel

### Component name

`FxRateTable`, `FxRateUploadPanel`

### Purpose

**Story 5.4 AC** — **FX rate table** with **effective date** and **source label** (manual upload v1); **no silent FX** — users can see **basis** for consolidation. **Optional rate API** is **out of scope v1** per requirements unless change request.

### Layout description

- **`FxRateUploadPanel`:** reuse **`ExcelDropZone`** (§2) + optional **`FilePreviewTable`** (§3) + primary **Upload** / **Import rates** (§8.2) + async outcome pattern from **`IngestionProgressTracker`** (§4) / **`ImportSuccessSummary`** (§6) as appropriate for rate batches — **⏸ architect** for API shape.
- **`FxRateTable`:** columns — **Currency pair** (or **From → To**) · **Rate** · **Effective date** · **Source** (e.g. Manual upload) · optional **Batch / file id** (monospace + **Copy**).
- Banner when rates missing for a period: `warning-surface` + `AlertTriangle` — explicit **no silent conversion** messaging.

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Table populated. |
| **Loading** | Skeleton rows. |
| **Empty** | “No FX rates loaded.” + pointer to upload. |

### Reuses Phase 1–4

- **`ImportBatchHistory`** (§7) table tone; **`ExcelDropZone`** / **`FilePreviewTable`**; **`HubSpotSyncHistoryTable`** (§29) for governance list patterns.

### ⏸ PO approval

- **Dedicated “Currencies” admin page** vs **section under Settings** — IA decision.

---

## 50. Consolidated monetary columns pattern

### Component name

`ConsolidatedMonetaryColumns` (pattern; implementation-flexible)

### Purpose

**Story 5.4 AC** — Consolidated views show **reporting currency** with access to **native currency** and **FX metadata** needed for Finance reconciliation (rate date, pair, reporting currency).

### Layout description

- **Primary** amount column: **reporting currency** with code in header or cell (§9).
- **Secondary** access: expandable row, tooltip, or adjacent **Native amount** column — **⏸ PO approval** for one pattern app-wide.
- **FX metadata** line (`text-small`, `text-secondary`): e.g. “Converted at **YYYY-MM-DD** using **EUR→USD** rate **x.xxxxxx**; source: **Manual upload**.”

### Reuses Phase 1–4

- **`RevenueFactsTable`** (§8) money columns; **`PeriodComparisonPanel`** (§12) explicit labels; design system §9.

### ⏸ PO approval

- **Heatmap or directional color** for FX gain/loss — **new data-viz pattern**; not in baseline; prefer neutral tabular copy.

---

## 51. AppSidebar — Phase 5 extension (delta to §1 / §17 / §25 / §32)

| Addition | Spec |
|----------|------|
| **New items (optional)** | Routes for **`ForecastingPage`** (§33), **`ProfitabilityPage`** (§39), **`CustomerSegmentsPage`** (§44), and/or **Currencies / FX** (§49) — labels **⏸ PO approval**; **order** relative to Import · Revenue · Analytics · Ask · Integrations **⏸ PO approval**. |
| **Icons (lucide)** | Suggested: `TrendingUp` (forecast) — **⏸ PO approval**; `Percent` or `PieChart` for profitability — **⏸ PO approval** (pie icon may imply charts); `Users` or `Filter` for segments; `Coins` or `Banknote` for FX — pick one consistent set without vendor glyphs. |
| **Gating** | Finance vs BU vs Admin for **rate upload** and **allocation edits** — **⏸ PO** (align §1 **Disabled** nav with tooltip). |

**Reuse:** All §1 / §17 / §25 / §32 behaviors (active, hover, focus, responsive).

---

## Phase 6 — New vs reused (summary)

Requirements source: [`phase-6-requirements.md`](../requirements/phase-6-requirements.md) (Stories **6.1–6.4**). Phase 6 is **governance and operations** around Phases 1–5: **SSO**, **audit export**, **enterprise admin** (security posture, pilot visibility), and **operational visibility** for integrations and background work. Phase 1–5 specs (§1–51) remain the baseline; Phase 6 **adds** admin and operator surfaces using established tokens, cards, tables, banners, and toolbars from `docs/design/design-system.md`.

| Feature (story) | New screens / components | Reuses Phase 5 (and earlier) |
|-----------------|---------------------------|------------------------------|
| **6.1** Enterprise SSO | **`EnterpriseSsoPage`** (shell); **`IdpProtocolSection`** (OIDC vs SAML fields per architect — non-secret config only in UI); **`DomainAllowlistEditor`**; **`ProvisioningModeControl`** (JIT vs invite-only); **`IdpGroupRoleMappingTable`** (explicit mappings); **`SsoStatusSummaryCard`**; optional **`SsoUserErrorPage`** / callback error region (**user-safe** copy) | `AppSidebar` (§1, §51); **forms** design system §8.1–8.4; **primary/secondary** buttons §8.2; **`HubSpotConnectionCard`** (§27) **card chrome** for status + actions; **`NLQuerySafetyMessage`** (§23) **severity** pattern for non-leaky errors; table density from **`NLQueryAuditTable`** (§24) |
| **6.2** Audit export & retention | **`AuditExportPage`** (shell); **`AuditExportScopePanel`** (event families, date range, format **CSV / JSON Lines** — fixed in design); **`AuditExportActionBar`** (download, `audit_export` permission messaging); **`AuditRetentionPolicyNotice`** (365-day operational default + docs link); optional **`AuditExportLoggedBanner`** after high-risk export | **`AnalyticsFilterToolbar`** (§11) **density** for filters; **`NLQueryAuditLogPage`** / **`NLQueryAuditTable`** (§24) **append-only** table tone; **`ImportBatchHistory`** (§7) / **`HubSpotSyncHistoryTable`** (§29) for governance lists; UUID/copy §8–9; **`ImportSuccessSummary`** (§6) timestamp + TZ label §8.5 |
| **6.3** Enterprise admin — security & pilot | **`EnterpriseGovernancePage`** (shell) **or** **tabbed admin** grouping SSO, audit, currency, integrations — **⏸ PO approval** (IA); **`IntegrationAuthorityPanel`** (who may connect HubSpot, upload FX — labels from API); **`ReportingCurrencyGovernanceSection`** (visibility + change path — not a new currency engine); **`FinanceFreezeWindowsCallout`** (docs link / in-product copy — **no** in-product calendar unless PO adds) | **`TenantReportingCurrencyIndicator`** (§48); **`FxRateUploadPanel`** / **`FxRateTable`** (§49) **entry points** for rate upload authority; **`HubSpotIntegrationPage`** (§26) for integration ownership context; **`AccessScopeIndicator`** (§15) placement discipline; cards **`ResolvedInterpretationPanel`** (§20), **`HubSpotConnectionCard`** (§27) |
| **6.4** Operational visibility | **`OperationalHealthPage`** (shell) **or** **section** under Integrations — **⏸ PO approval**; **`IntegrationHealthOverview`** (HubSpot + ingest + job summary **without** false green); **`BackgroundJobsTable`** (failed/stuck Celery jobs, links to retry/support per product); navigation **aggregation** to existing HubSpot detail | **`HubSpotIntegrationPage`** (§26); **`HubSpotConnectionCard`** (§27); **`HubSpotSyncStatusPanel`** (§28); **`HubSpotSyncHistoryTable`** (§29); **`IngestionProgressTracker`** (§4); **`ImportBatchHistory`** (§7); **`AnalyticsQueryProgress`** (§16); **`ImportErrorList`** (§5) banner severity for partial failure |

**Does not introduce new core analytics UI:** Phase 5 feature areas (**Forecasting**, **Profitability**, **Segments**, **FX**) remain as specified in §33–50; Phase 6 only adds **governance** around them (access, audit export, authority).

**⏸ PO approval — IA / shell:** Single **“Enterprise”** / **“Security”** / **“Admin”** area vs **Settings** sub-routes vs **split** SSO page + Audit page + Ops page — same class of decision as §9, §18, §26; **do not** invent a fourth top-level navigation pattern without PO sign-off.

**⏸ PO approval — new patterns:** **Full-page SSO login** branded shell vs **minimal** redirect-only (most UX is IdP-hosted); **wizard** for first-time IdP setup vs **single long form**; **dedicated** `SsoUserErrorPage` vs **inline** alert on return URL — architect and PO should align before implementation.

---

## 52. Enterprise SSO page (shell)

### Component name

`EnterpriseSsoPage` (route-level view; name implementation-flexible)

### Purpose

**Story 6.1** — Host **OIDC and SAML** non-secret IdP configuration (metadata URL or XML upload path per architect), **domain allowlist**, **JIT vs invite-only** provisioning mode, optional **IdP group → app role** explicit mappings, and **SSO enabled/disabled** status for the tenant — **no** hardcoded IdP secrets in UI (secrets via environment or secure ops paths per PRD).

### Layout description

- **Page title** (`text-display`): e.g. **“Single sign-on (SSO)”** or **“Enterprise sign-on”** — exact copy **⏸ PO approval**.
- Short supporting line (`text-small`, `text-secondary`): one sentence that **application roles remain authoritative** and mappings are **optional and explicit** (Approved product decisions).
- Vertical stack: **`SsoStatusSummaryCard`** → **`IdpProtocolSection`** (OIDC block **and/or** SAML block per enabled protocol — **⏸ architect**) → **`DomainAllowlistEditor`** → **`ProvisioningModeControl`** → **`IdpGroupRoleMappingTable`** (optional section when tenant uses mappings).
- **Horizontal padding / section gaps:** design system §3 (`space-6` desktop).

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Sections populated or guided empty states for first-time setup. |
| **Loading** | Skeleton cards; save actions disabled while loading. |
| **Error** | Inline alert (`error` / `error-surface`) + **Retry** (§8.2); **no** raw IdP or stack traces (AC). |
| **Forbidden** | User-safe message if role lacks admin SSO permission — pattern consistent with **`NLQueryAuditLogPage`** forbidden (§24). |

### Content

- **Icons (lucide):** `Shield`, `KeyRound`, or `Lock` for security context — **⏸ PO approval**; `Link2` for connection metadata (align §26).

### Interaction

| Action | Result |
|--------|--------|
| Save / validate IdP config | API validates metadata or OIDC discovery — surface **actionable** errors for IT (invalid URL, cert, issuer) without leaking internals. |

### Responsive behaviour

- **Tablet:** Stack sections full width; forms single column.

### Reuses Phase 1–5

- Page shell from **`AnalyticsPage`** (§9), **`HubSpotIntegrationPage`** (§26).

### ⏸ PO approval

- **Tabbed OIDC | SAML** vs **single page** with both — pick one; **wizard** for first connection is **⏸ PO approval** (may be a **new flow pattern** if not used elsewhere).

---

## 53. IdP protocol section (OIDC / SAML non-secret fields)

### Component name

`IdpProtocolSection`

### Purpose

**Story 6.1** — Collect **admin-managed** IdP endpoints and identifiers **excluding secrets** where those must live in secure configuration (per architect). Supports **OIDC first, SAML in same release** (Approved product decisions).

### Layout description

- **Card** (`surface-elevated`, `radius-md`, `shadow-sm`, `space-6` padding).
- **OIDC (example fields — exact manifest ⏸ architect):** Issuer / authority URL, client id **if** safe to display, redirect URI **read-only** copy box, scopes — **no** client secret in plain UI.
- **SAML (example fields):** Metadata URL **or** metadata XML upload **or** paste — **⏸ architect**; ACS URL / entity ID **read-only** copy where applicable.
- Helper text (`text-small`, `text-secondary`) pointing to **secure** secret rotation outside plain text — **⏸ PO/compliance**.

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Editable non-secret fields. |
| **Validating** | Primary **Save** shows `Loader2` + `aria-busy`. |
| **Invalid metadata** | Field-level or banner `error` — user-safe string (AC). |

### Reuses Phase 1–5

- Inputs §8.1; **`HubSpotConnectionCard`** (§27) card structure; **`ImportSuccessSummary`** (§6) **Copy** pattern for URLs.

---

## 54. Domain allowlist editor

### Component name

`DomainAllowlistEditor`

### Purpose

**Story 6.1** — **JIT provisioning** when user email **domain** is on tenant **allowlist**; clear **audit** expectation on first login (backend); UI is **add/remove** domains with validation (no wildcards unless architect specifies).

### Layout description

- Section title (`text-heading`): **“Approved email domains”** — **⏸ PO approval**.
- **List** of domains (`text-body`) with **Remove** (ghost or danger compact §8.2); **Add** row: text input + **Add domain** primary/secondary.
- Inline validation: invalid domain format — `error` border + `AlertCircle` (§8.1).

### Visual states

| State | Appearance |
|-------|--------------|
| **Empty** | Helper line: JIT requires at least one domain **unless** invite-only mode — **⏸ PO approval** for exact copy. |

### Reuses Phase 1–5

- Form controls §8; list editing pattern similar to **tag/chip** lists using `radius-sm` and `space-2`.

---

## 55. Provisioning mode control

### Component name

`ProvisioningModeControl`

### Purpose

**Story 6.1** — Toggle **JIT (default)** vs **invite-only** (disable JIT) per Approved product decisions; **audited** when changed (backend).

### Layout description

- **Radio group** or **select** (§8.3): **JIT with domain allowlist** · **Invite only** (labels **⏸ PO approval**).
- Short description under each (`text-small`, `text-secondary`).

### Reuses Phase 1–5

- **`DisambiguationPanel`** (§22) radio/list semantics; design system §8.

---

## 56. IdP group → role mapping table

### Component name

`IdpGroupRoleMappingTable`

### Purpose

**Story 6.1** — **Optional** explicit table: **IdP group identifier** → **application role**; **no** implicit sync-all (Approved product decisions).

### Layout description

- Section title (`text-heading`): **“Group to role mappings”** — **⏸ PO approval**.
- Table columns — **IdP group id** (or claim value) · **App role** · **Actions** (remove); **Add mapping** opens row or modal — **⏸ PO approval** (modal is acceptable if product already uses modals elsewhere; else inline row — **⏸ PO approval** as **new pattern** if modals are net-new to shell).

### Visual states

| State | Appearance |
|-------|--------------|
| **Empty** | “No mappings — application roles are assigned by administrators unless you add mappings.” — **⏸ PO approval**. |

### Reuses Phase 1–5

- **`NLQueryAuditTable`** (§24), **`EntityMappingExceptionsTable`** (§30) read-only density; editable variant uses same row height §9.

### ⏸ PO approval

- **Net-new modal pattern** for “Add mapping” if the product has not shipped modals — flag PO before build.

---

## 57. SSO status summary card

### Component name

`SsoStatusSummaryCard`

### Purpose

**Stories 6.1, 6.3** — At-a-glance **SSO enabled**, protocol in use, and **last successful** validation or login **if** API provides — supports IT runbooks without duplicating full IdP form.

### Layout description

- **Card** matching **`HubSpotConnectionCard`** (§27): status **badge** (`text-micro`), `text-body-strong` title, `text-small` metadata lines.

### Visual states

| State | Appearance |
|-------|--------------|
| **SSO required / healthy** | Success or neutral badge per PO tone — **⏸ PO approval** (avoid false green if IdP degraded — align **6.4** health semantics). |
| **Misconfiguration** | `warning-surface` or `error-surface` + short line + link to **`IdpProtocolSection`**. |

### Reuses Phase 1–5

- **`HubSpotConnectionCard`** (§27) layout and badges.

---

## 58. SSO user-facing error page / region

### Component name

`SsoUserErrorPage` (full route) **or** `SsoCallbackErrorPanel` (embedded)

### Purpose

**Story 6.1 AC** — IdP unreachable, invalid metadata, token validation failure: **clear, non-leaky** errors for end users; **actionable** cues for IT (support reference id **⏸ PO approval** if used).

### Layout description

- **Centered** content column (max-width consistent with app shell): `surface-elevated`, `radius-lg`, `shadow-lg`, padding `space-8`.
- **Headline** (`text-heading`): plain language — e.g. **“Sign-in didn’t complete”** — **⏸ PO approval**.
- **Body** (`text-body`, `text-secondary`): no stack traces; optional **Try again** / **Contact IT** — **⏸ PO approval**.
- Icon: `AlertCircle` or `ShieldOff` (lucide, 20–24px).

### Reuses Phase 1–5

- **`NLQuerySafetyMessage`** (§23) tone; design system §1 error surfaces.

### ⏸ PO approval

- **Full-page** dedicated route vs **inline** panel on login shell — pick one; **new** if product currently has no marketing-style centered error page.

---

## 59. Audit export page (shell)

### Component name

`AuditExportPage` (route-level view; name implementation-flexible)

### Purpose

**Story 6.2** — Authorized users with the `audit_export` permission **request** and **download** audit evidence covering **imports/batches**, **NL query audit**, **HubSpot sync**, and **SSO/security** events — formats **CSV or JSON Lines** (**fixed in design**); export is **logged** as high-risk where appropriate.

### Layout description

- **Page title** (`text-display`): e.g. **“Audit export”** — **⏸ PO approval**.
- **`AuditRetentionPolicyNotice`** at top (operational retention + link to policy docs).
- **`AuditExportScopePanel`**: event family checkboxes or multi-select, **date range** (§8.5), **format** (CSV | JSON Lines).
- **`AuditExportActionBar`**: primary **Export** / **Download** with loading state; secondary **Clear** optional.
- Optional **preview** table (first N rows) — **⏸ PO approval** (heavy queries).

### Visual states

| State | Appearance |
|-------|--------------|
| **Default** | Form ready. |
| **Loading** | Button `Loader2`; optional size warning for large exports — **⏸ PO approval**. |
| **Forbidden** | Same as §24 / §52 forbidden pattern. |
| **Success** | Browser download + optional **`AuditExportLoggedBanner`** (info line that action was recorded). |

### Content

- **Field manifest** for export columns — **exact list ⏸ architect** (AC: fixed in design).

### Reuses Phase 1–5

- **`NLQueryAuditLogPage`** (§24) intro + retention copy pattern; **`AnalyticsPage`** (§9) shell.

---

## 60. Audit export scope panel

### Component name

`AuditExportScopePanel`

### Purpose

**Story 6.2** — Map AC **export scope** to UI: which **event families**, **time bounds**, and **output format**.

### Layout description

- **Card** or form region with `space-4` between field groups.
- **Event families** — minimum labels: **Imports / batches** · **Natural language queries** · **HubSpot sync** · **SSO / security** — exact enums **⏸ architect**.
- **Date range:** paired inputs or range picker §8.5; label “Times in your local timezone” where relevant.
- **Format:** segmented control or radio — **CSV** · **JSON Lines** (`.jsonl`).

### Reuses Phase 1–5

- **`AnalyticsFilterToolbar`** (§11) control density; checkboxes §8.4.

---

## 61. Audit export action bar

### Component name

`AuditExportActionBar`

### Purpose

**Story 6.2** — Primary **download** action with **permission** copy: users understand export is **authorized** and **sensitive** (Finance/IT review).

### Layout description

- Horizontal row: primary button **Export** / **Download** (§8.2); inline `text-small` **permission** line: e.g. “Requires **Audit export** permission; activity may be logged.” — **⏸ PO/legal**.

### Reuses Phase 1–5

- Buttons §8.2; **`ImportSuccessSummary`** (§6) key-value **clarity** for disclaimers.

---

## 62. Audit retention policy notice

### Component name

`AuditRetentionPolicyNotice`

### Purpose

**Story 6.2 AC** — **Surface** operational retention (**365 days** default in primary store) so pilots are not surprised; link to **documentation** for long-term policy (not legal advice in UI).

### Layout description

- **Non-blocking** strip or inset: `primary-muted` or `surface-subtle`; `text-small`; icon `Info` optional.
- Copy pattern: “**Operational retention:** …” + **Learn more** → docs — **⏸ PO/compliance** for final wording.

### Reuses Phase 1–5

- **`AnalyticsFreshnessBanner`** (§14), **`ForecastDisclaimerBanner`** (§34) **non-blocking** placement discipline.

---

## 63. Audit export logged banner (optional)

### Component name

`AuditExportLoggedBanner`

### Purpose

**Story 6.2** — After successful export, **optional** confirmation that the action was **recorded** (high-risk logging) — **no** scare copy unless PO wants stronger tone.

### Layout description

- `primary-muted` or `success-surface` **thin** banner; `text-small`; `CheckCircle2` optional.

### Reuses Phase 1–5

- **`ImportSuccessSummary`** (§6) success tone without chart clutter.

---

## 64. Enterprise governance page (shell)

### Component name

`EnterpriseGovernancePage` (route-level view; name implementation-flexible)

### Purpose

**Story 6.3** — Single **admin** destination (or **tab** set — **⏸ PO approval**) for **pilot-contract visibility**: **SSO status**, **session-related** settings **where exposed**, **reporting currency** visibility and **change-controlled** path, **integration authority** (HubSpot connect, FX upload), and **links** to **Finance freeze windows** (calendar enforcement **out of scope** unless PO adds — Phase 6 doc).

### Layout description

- **Page title** (`text-display`): e.g. **“Enterprise settings”** / **“Security & governance”** — **⏸ PO approval**.
- Vertical stack: **`SsoStatusSummaryCard`** (§57) with link to **`EnterpriseSsoPage`** (§52) → **`ReportingCurrencyGovernanceSection`** (§65) → **`IntegrationAuthorityPanel`** (§66) → **`FinanceFreezeWindowsCallout`** (§67).
- All changes to **security-sensitive** settings are **audited** (backend); UI shows **Save** busy states §8.2.

### Visual states

| State | Appearance |
|-------|--------------|
| **Loading** | Skeleton sections. |
| **Error** | Inline alert + **Retry** (§8.2). |

### Reuses Phase 1–5

- **`HubSpotIntegrationPage`** (§26) multi-section vertical stack; **`AnalyticsPage`** (§9) title pattern.

### ⏸ PO approval

- **One page** vs **separate** SSO / Audit / Ops routes only — IA § Phase 6 summary.

---

## 65. Reporting currency governance section

### Component name

`ReportingCurrencyGovernanceSection`

### Purpose

**Stories 6.2 (visibility), 6.3, Approved product decision 8** — **Surface** tenant **reporting currency** (default **USD**); **non-USD** set at provisioning or **existing admin path** (Phase 5) — Phase 6 **does not** add a new currency engine; UI makes **visibility** and **who may change** explicit.

### Layout description

- **Card** with **`TenantReportingCurrencyIndicator`** (§48) **embedded** or repeated for emphasis.
- If editable: same **select** pattern as Phase 5 **⏸ PO approval** for who may edit (role-gated); **confirmation** step for change — **⏸ PO approval** if net-new **confirm modal** (flag PO if modals are new to product).

### Reuses Phase 1–5

- **`TenantReportingCurrencyIndicator`** (§48); **`FxRateTable`** / **`FxRateUploadPanel`** (§49) **related links** for FX governance.

---

## 66. Integration authority panel

### Component name

`IntegrationAuthorityPanel`

### Purpose

**Story 6.3** — Show **who may** connect **HubSpot**, **upload FX rates**, and other **integration** actions **without** developer-only config files — read-only **matrix** or **list** **⏸ architect**.

### Layout description

- Section title (`text-heading`): **“Integration permissions”** — **⏸ PO approval**.
- Table or definition list: **Action** · **Roles / users allowed** (as API returns) — **append-only** feel (no casual edit unless product ships ACL editor — **⏸ PO approval**).

### Visual states

| State | Appearance |
|-------|--------------|
| **Empty / not configured** | Neutral explanation + link to admin docs — **⏸ PO approval**. |

### Reuses Phase 1–5

- **`CostAllocationSummaryPanel`** (§42) **read-only** governance tone; table density §9.

---

## 67. Finance freeze windows callout

### Component name

`FinanceFreezeWindowsCallout`

### Purpose

**Story 6.3 AC** — **Reference** parent PRD **Finance freeze windows** via **documentation** link or short **in-product** copy; **in-product calendar enforcement** is **optional / out of scope** unless listed in Phase 6 scope.

### Layout description

- **Inset** `primary-muted` card or **inline** paragraph: `text-small` + **external** or **internal** doc link (opens new tab — accessible name).

### Reuses Phase 1–5

- **`ForecastDisclaimerBanner`** (§34) inset discipline; link styling **primary** color §1.

---

## 68. Operational health page (shell)

### Component name

`OperationalHealthPage` (route-level view; name implementation-flexible)

### Purpose

**Story 6.4** — **Consolidated** IT view: **HubSpot** connection and **recent sync** outcomes, **Excel ingest** / batch health **where surfaced**, **background jobs** (Celery) **failed or stuck**, **actionable** errors — **no false “green”** when partial failures occurred (align Phase 4/5 semantics).

### Layout description

- **Page title** (`text-display`): e.g. **“Integrations & jobs”** / **“Operational health”** — **⏸ PO approval**.
- Short line (`text-small`): runbook-oriented — **⏸ PO approval**.
- Vertical stack: **`IntegrationHealthOverview`** → deep links or embedded summaries to **`HubSpotConnectionCard`**, **`HubSpotSyncStatusPanel`**, **`HubSpotSyncHistoryTable`** (§27–29) → **`BackgroundJobsTable`** → optional **Import** summary strip linking to **Import** route + **`ImportBatchHistory`** (§7).

### Visual states

| State | Appearance |
|-------|--------------|
| **Degraded** | Section-level `warning-surface` / `error-surface` when any subsystem unhealthy — **visible** without requiring drill-down. |
| **Loading** | Skeleton cards. |

### Reuses Phase 1–5

- **`HubSpotIntegrationPage`** (§26) **composition**; **`AnalyticsFreshnessBanner`** (§14) **non-blocking** vs **health** emphasis — **⏸ PO approval** for severity balance.

### ⏸ PO approval

- **Dedicated** route vs **anchor** on **`EnterpriseGovernancePage`** (§64) — IA.

---

## 69. Integration health overview

### Component name

`IntegrationHealthOverview`

### Purpose

**Story 6.4** — **Aggregate** row or card strip: **HubSpot** status, **last ingest** or **last batch** outcome summary, **jobs** attention count — each links to detail **without** duplicating inconsistent logic (single source of truth from APIs).

### Layout description

- **Responsive** grid or horizontal **summary cards** (`shadow-sm`, `radius-md`, `space-4` padding): one card **HubSpot**, one **Imports**, one **Background jobs** — labels **⏸ PO approval**.
- **Status** uses badges §1 semantic colors; **partial failure** must show **warning**, not success (AC).

### Reuses Phase 1–5

- **`HubSpotConnectionCard`** (§27) **condensed** metrics; **`ImportBatchHistory`** (§7) **last row** summary pattern.

---

## 70. Background jobs table

### Component name

`BackgroundJobsTable`

### Purpose

**Story 6.4** — List **failed** or **stuck** jobs (Celery semantics per backend) with **context** for **retry** or **support** (links or IDs **⏸ architect**); paginated or **time-bounded** for performance (AC).

### Layout description

- Table columns — **Job type** · **Started** · **Ended** / **Duration** · **Status** · **Summary** · **Actions** (view detail, copy id) — **exact set ⏸ architect**.
- **Stuck** state row: `warning-surface` highlight or `AlertTriangle` icon — **⏸ PO approval** for emphasis rules.

### Visual states

| State | Appearance |
|-------|--------------|
| **Empty (no failures)** | Positive neutral line: “No failed jobs in selected window.” — optional link to full job log — **⏸ PO approval**. |

### Reuses Phase 1–5

- **`HubSpotSyncHistoryTable`** (§29), **`ImportBatchHistory`** (§7); monospace + **Copy** §8–9.

---

## 71. AppSidebar — Phase 6 extension (delta to §1 / §51)

| Addition | Spec |
|----------|------|
| **New items (optional)** | **Enterprise / Security**, **Audit export**, **Operations** / **Health** — labels and **order** **⏸ PO approval**; routes to **`EnterpriseSsoPage`** (§52), **`AuditExportPage`** (§59), **`OperationalHealthPage`** (§68), or **combined** **`EnterpriseGovernancePage`** (§64). |
| **Icons (lucide)** | `Shield` or `Settings` for governance — **⏸ PO approval**; `Download` or `FileJson` for audit export; `Activity` or `HeartPulse` for ops health — pick **one** consistent set. |
| **Gating** | **IT Admin** / **`audit_export`** / integration admin — **⏸ PO**; items **disabled** with tooltip **“No access”** (§1) when role lacks permission. |

**Reuse:** All §1 / §51 behaviors (active, hover, focus, responsive).

---

*End of document.*
