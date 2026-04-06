# Design System — Phase 1 (Foundation)

| Field | Value |
|--------|--------|
| **Status** | **Approved (PO)** — 2026-04-03 |
| **Scope** | Phase 1 UI; extend in later phases |
| **Icons** | **lucide-react** (mandated) |
| **Revision** | 2026-04-03 — Status aligned with PO-approved UX package (`user-flows`, `component-specs`, `ux-decisions`). |

Define once; all Phase 1 components (`component-specs.md`) consume these tokens. Implementation may use CSS variables, Tailwind theme extension, or design tokens JSON—Tech Lead choice as long as visual output matches.

---

## 1. Color palette

Semantic naming for light theme (default for Phase 1). Dark mode is **out of scope** unless PO requests; if added later, mirror semantic roles.

| Token | Role | Example hex (HSL-friendly) | Usage |
|-------|------|------------------------------|--------|
| `--color-primary` | Primary actions, key focus | `#0F766E` (teal 700) | Primary buttons, active nav indicator, links |
| `--color-primary-hover` | Primary hover | `#0D9488` (teal 600) | Button hover |
| `--color-primary-muted` | Primary subtle backgrounds | `teal-50` / `#F0FDFA` | Selected row tint, info banners |
| `--color-accent` | Highlights, drag-over | `#0369A1` (sky 700) | Drop zone active state, secondary emphasis |
| `--color-success` | Positive outcome | `#15803D` (green 700) | Success summary, completed steps |
| `--color-success-surface` | Success background | `#F0FDF4` | Success card background |
| `--color-warning` | Caution, overlap risk | `#B45309` (amber 700) | Replace confirmation, non-blocking warnings |
| `--color-warning-surface` | Warning background | `#FFFBEB` | Warning banners |
| `--color-error` | Failure, destructive emphasis | `#B91C1C` (red 700) | Errors, failed step, validation |
| `--color-error-surface` | Error background | `#FEF2F2` | Error list region |
| `--color-surface-page` | App background | `#F8FAFC` (slate 50) | Main canvas |
| `--color-surface-elevated` | Cards, sidebar | `#FFFFFF` | Cards, modals, sidebar |
| `--color-surface-subtle` | Muted panels | `#F1F5F9` (slate 100) | Table stripe, disabled inputs |
| `--color-text-primary` | Body text | `#0F172A` (slate 900) | Primary copy |
| `--color-text-secondary` | Supporting text | `#475569` (slate 600) | Hints, metadata |
| `--color-text-muted` | Placeholder, disabled | `#94A3B8` (slate 400) | Disabled, placeholders |
| `--color-text-inverse` | On dark buttons | `#FFFFFF` | Primary button label |
| `--color-border` | Default borders | `#E2E8F0` (slate 200) | Cards, inputs, table lines |
| `--color-border-strong` | Emphasis borders | `#CBD5E1` (slate 300) | Focus rings, dividers |
| `--color-focus-ring` | Accessibility | `primary` at 2px + 2px offset | Keyboard focus |

**Finance / trust:** Avoid pure reds/greens for **data** meaning (accessibility); use **position** (sign column), **icons**, and **labels** for directionality. Currency columns use **neutral** text color with tabular numerals.

---

## 2. Typography scale

**Font stack:** `ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`

**Numeric / money (optional second family):** `"SF Mono", ui-monospace, "Cascadia Mono", "Segoe UI Mono", monospace` for amount and UUID columns only.

| Token | Size | Weight | Line height | Letter spacing | Use case |
|-------|------|--------|-------------|----------------|----------|
| `text-display` | 1.875rem (30px) | 600 | 1.2 | -0.02em | Page titles (Import, Revenue) |
| `text-heading` | 1.25rem (20px) | 600 | 1.3 | -0.01em | Section titles, card titles |
| `text-body` | 0.875rem (14px) | 400 | 1.5 | normal | Body, table cells |
| `text-body-strong` | 0.875rem (14px) | 500 | 1.5 | normal | Table headers, labels |
| `text-small` | 0.8125rem (13px) | 400 | 1.45 | normal | Helper text, captions |
| `text-micro` | 0.75rem (12px) | 500 | 1.4 | 0.02em | Badges, column tags (uppercase optional) |

**Rules**

- **Single page title** per view (`text-display`).
- **Sentence case** for UI strings (except acronyms: API, UUID, BU).
- **No all-caps body**; micro labels may use uppercase with increased tracking sparingly.

---

## 3. Spacing system

**Base unit:** `4px` (`0.25rem`)

| Token | Value | Typical use |
|-------|-------|-------------|
| `space-0` | 0 | Collapse |
| `space-1` | 4px | Tight icon gaps |
| `space-2` | 8px | Inline icon + text |
| `space-3` | 12px | Form field vertical rhythm |
| `space-4` | 16px | Card padding (compact), stack gap |
| `space-5` | 20px | Section gap |
| `space-6` | 24px | Card padding (comfortable) |
| `space-8` | 32px | Page section separation |
| `space-10` | 40px | Major layout breaks |
| `space-12` | 48px | Page top/bottom padding |

**Layout**

- **Page horizontal padding:** `space-6` desktop, `space-4` tablet.
- **Form field gap:** `space-3` between label and input; `space-4` between fields.
- **Card internal padding:** `space-6`.

---

## 4. Border radius

| Token | Value | Use |
|-------|-------|-----|
| `radius-sm` | 4px | Inputs, small chips |
| `radius-md` | 8px | Buttons, cards, drop zone |
| `radius-lg` | 12px | Modals, large panels |
| `radius-full` | 9999px | Avatars, pills |

---

## 5. Shadow levels

| Token | CSS (example) | Use |
|-------|-----------------|-----|
| `shadow-none` | none | Flat regions |
| `shadow-sm` | `0 1px 2px rgb(15 23 42 / 0.06)` | Cards at rest |
| `shadow-md` | `0 4px 6px -1px rgb(15 23 42 / 0.08)` | Dropdowns, popovers |
| `shadow-lg` | `0 10px 15px -3px rgb(15 23 42 / 0.1)` | Modals, mobile drawer |

---

## 6. Icon library

- **Library:** **lucide-react** only for Phase 1 product UI (consistency, tree-shakeable).
- **Sizing:** 16px default inline; 20px in empty states; 24px hero empty illustration icon.
- **Stroke:** Default Lucide stroke width; do not mix filled icon sets.
- **Pairing:** Icon + label for sidebar; icon-only only with `aria-label` and tooltips (collapsed nav).

**Suggested mapping**

| Concept | Lucide icon |
|---------|-------------|
| Import / upload | `Upload`, `FileUp` |
| Spreadsheet | `FileSpreadsheet` |
| Revenue / table | `Table` |
| Success | `CheckCircle2` |
| Error | `AlertCircle`, `XCircle` |
| Warning | `AlertTriangle` |
| Copy | `Copy` |
| Loading | `Loader2` (animate spin) |
| Organization | `Building2` |
| Calendar / period | `CalendarRange` |

---

## 7. Animation and transition standards

| Property | Value |
|----------|--------|
| **Duration fast** | 120ms — hover color, border |
| **Duration base** | 200ms — opacity, shadow, drawer |
| **Duration slow** | 300ms — modal enter/exit |
| **Easing default** | `cubic-bezier(0.4, 0, 0.2, 1)` |
| **Easing enter** | `cubic-bezier(0, 0, 0.2, 1)` |
| **Easing exit** | `cubic-bezier(0.4, 0, 1, 1)` |

**Rules**

- **Respect `prefers-reduced-motion`:** replace motion with instant state change or opacity-only.
- **No infinite animation** except explicit loading spinners on active work.
- **Skeleton loaders** use subtle pulse (opacity 0.6 ↔ 1) with 1.2s ease-in-out if motion allowed.

---

## 8. Form element standards

### 8.1 Input (text, email)

- Height **40px** min; padding horizontal `space-3`; `radius-sm` border `border`.
- **Focus:** 2px ring `color-focus-ring`; border `primary`.
- **Error:** Border `error`; `text-small` error message below in `error` color with `AlertCircle` 14px.
- **Disabled:** Background `surface-subtle`, text `text-muted`.

### 8.2 Button

| Variant | Background | Text | Border |
|---------|------------|------|--------|
| Primary | `primary` | `text-inverse` | none |
| Secondary | `surface-elevated` | `text-primary` | `border` |
| Ghost | transparent | `primary` | none |
| Danger | `error` | `text-inverse` | none (destructive confirm only) |

- **Height:** 40px default; 32px compact in dense tables.
- **Padding:** horizontal `space-4` (default), `space-3` (compact).
- **Loading:** Replace label with `Loader2` + “Saving…” / “Importing…”; `disabled` + `aria-busy="true"`.

### 8.3 Dropdown / select

- Native `<select>` acceptable Phase 1 for org picker; custom listbox must have **keyboard** (↑↓, Enter, Esc) and **aria-activedescendant** if custom.
- **Menu max-height:** ~320px with scroll; `shadow-md`.

### 8.4 Checkbox

- 18px hit target minimum; label clickable; focus ring on box.
- **Replace** flow: checkbox + warning `warning-surface` banner when checked.

### 8.5 Date range (period)

- Paired inputs or single range picker; ISO `YYYY-MM-DD` display consistent with API; timezone label: “Times in your local timezone” for completion timestamps.

---

## 9. Data display

- **Money:** Format with locale-aware thousands separators; **always** show currency code in column or header (`USD`).
- **UUID:** Monospace `text-small`; truncate middle with **Copy** affordance.
- **Table density:** Comfortable row height **44px** minimum (touch + readability).

---

*End of document.*
