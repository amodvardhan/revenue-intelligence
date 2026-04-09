import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, MessageSquarePlus, Pencil } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/services/api";

const phase7 = import.meta.env.VITE_ENABLE_PHASE7 === "true";

function parseAmountStr(v: string): number {
  const n = parseFloat(String(v).replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

interface OrgList {
  items: Array<{ org_id: string; org_name: string }>;
}

interface RevenueRow {
  revenue_id: string;
  amount: string;
  currency_code: string;
  revenue_date: string;
  org_id: string;
  business_unit_id: string | null;
  division_id: string | null;
  source_system: string;
  batch_id: string | null;
}

interface RevenueListResponse {
  items: RevenueRow[];
  next_cursor: string | null;
}

interface MatrixMonthColumn {
  key: string;
  label: string;
}

interface MatrixLine {
  row_type: "value" | "delta";
  sr_no: number | null;
  customer_id: string | null;
  customer_legal: string;
  customer_common: string | null;
  amounts: string[];
  amounts_editable?: boolean;
  variance_comments?: (string | null)[] | null;
  variance_comments_editable?: boolean;
}

interface RevenueMatrixResponse {
  currency_code: string;
  month_columns: MatrixMonthColumn[];
  lines: MatrixLine[];
  empty_reason: string | null;
  matrix_scope?: "organization" | "business_unit" | "division";
}

interface BusinessUnitItem {
  business_unit_id: string;
  business_unit_name: string;
}

interface DivisionItem {
  division_id: string;
  division_name: string;
}

const MATRIX_DENSITY_KEY = "revenue-matrix-density";

function MatrixAmountInput({
  amount,
  disabled,
  onCommit,
  compact,
}: {
  amount: string;
  disabled?: boolean;
  onCommit: (next: string) => void;
  compact?: boolean;
}) {
  const [v, setV] = useState(amount);
  useEffect(() => setV(amount), [amount]);
  return (
    <input
      type="text"
      inputMode="decimal"
      className={`box-border w-full max-h-full rounded border border-transparent bg-transparent px-1 text-right font-mono tabular-nums text-ink hover:border-black/[0.08] focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25 ${
        compact ? "min-w-[4.25rem] py-0 text-[11px] leading-none" : "min-w-[5.5rem] py-0.5 text-[13px]"
      }`}
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => {
        if (v.trim() === amount.trim()) return;
        onCommit(v.trim());
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
      }}
      disabled={disabled}
      aria-label="Revenue amount"
    />
  );
}

function MomDeltaCell({ value }: { value: string }) {
  if (!value) return null;
  const n = parseFloat(value.replace(/,/g, ""));
  if (!Number.isFinite(n)) {
    return <span className="text-ink-muted">{value}</span>;
  }
  if (n === 0) {
    return <span className="text-neutral-500">{value}</span>;
  }
  const pos = n > 0;
  return (
    <span
      className={`inline-flex max-h-full items-center justify-end gap-0.5 whitespace-nowrap font-mono text-[11px] leading-none tabular-nums ${
        pos ? "text-emerald-700" : "text-red-700"
      }`}
    >
      {pos ? <ArrowUp className="h-3 w-3 shrink-0" aria-hidden /> : <ArrowDown className="h-3 w-3 shrink-0" aria-hidden />}
      {value}
    </span>
  );
}

const VARIANCE_MAX = 4000;

function VarianceNarrativeBlock({
  children,
  narrative,
  editable,
  focusKey,
  onSave,
  isSaving,
}: {
  children: ReactNode;
  narrative: string | null | undefined;
  editable: boolean;
  focusKey: string;
  onSave: (text: string) => Promise<void>;
  isSaving: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(narrative ?? "");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setDraft(narrative ?? "");
  }, [narrative]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const t = window.setTimeout(() => textareaRef.current?.focus(), 50);
    return () => {
      document.body.style.overflow = prev;
      window.clearTimeout(t);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isSaving) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, isSaving]);

  const hasText = Boolean(narrative?.trim());

  const modal =
    open &&
    createPortal(
      <div className="fixed inset-0 z-[200] flex items-end justify-center sm:items-center">
        <button
          type="button"
          className="absolute inset-0 z-0 cursor-default bg-[rgb(15_23_42/0.35)] backdrop-blur-[3px] transition-opacity"
          aria-label="Close dialog"
          disabled={isSaving}
          onClick={() => !isSaving && setOpen(false)}
        />
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="variance-narrative-title"
          className="relative z-10 flex max-h-[min(92vh,34rem)] w-full max-w-[min(100vw,26rem)] flex-col overflow-hidden rounded-t-[1.25rem] border border-black/[0.08] bg-white shadow-[0_25px_50px_-12px_rgba(15,23,42,0.22)] sm:mx-4 sm:rounded-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <header className="shrink-0 border-b border-black/[0.06] px-5 pb-4 pt-5 text-left">
            <h3 id="variance-narrative-title" className="text-heading text-[17px]">
              Explain this change
            </h3>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-muted">
              Describe why revenue moved versus the prior month. This appears with your matrix for finance and delivery
              leadership.
            </p>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            <label htmlFor="variance-narrative-field" className="sr-only">
              Variance explanation
            </label>
            <textarea
              id="variance-narrative-field"
              ref={textareaRef}
              className="input-modern box-border min-h-[148px] w-full resize-y py-3 font-sans text-[15px] leading-relaxed"
              maxLength={VARIANCE_MAX}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Example: milestone invoice in February; prior month was ramp-up only."
            />
            <div className="mt-2 flex justify-end">
              <span className="text-[12px] tabular-nums text-neutral-500">
                {draft.length.toLocaleString()} / {VARIANCE_MAX.toLocaleString()}
              </span>
            </div>
          </div>
          <footer className="flex shrink-0 items-center justify-end gap-3 border-t border-black/[0.06] bg-neutral-50/80 px-5 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <button type="button" className="btn-secondary-solid min-w-[5.5rem] px-5" disabled={isSaving} onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="btn-primary-solid min-w-[5.5rem] px-5"
              disabled={isSaving}
              onClick={() => {
                void (async () => {
                  try {
                    await onSave(draft.trim());
                    setOpen(false);
                  } catch {
                    /* parent surfaces error */
                  }
                })();
              }}
            >
              {isSaving ? "Saving…" : "Save"}
            </button>
          </footer>
        </div>
      </div>,
      document.body,
    );

  return (
    <>
      <div className="flex w-full min-w-0 items-center gap-0" data-vc-focus={focusKey}>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-1.5 overflow-hidden">
          {children}
          {hasText ? (
            <span
              className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary shadow-[0_0_0_2px_rgba(255,255,255,0.96)]"
              title={narrative ?? "Explanation on file"}
              aria-label="Explanation recorded for this month"
            />
          ) : null}
        </div>
        <div className="flex h-7 w-7 shrink-0 items-center justify-center">
          {editable ? (
            <button
              type="button"
              className="vc-narrative-hit flex h-7 w-7 items-center justify-center rounded-full border border-black/[0.08] bg-white/95 text-primary shadow-sm hover:border-primary/25 hover:bg-teal-50/40"
              title={hasText ? "Edit explanation" : "Add explanation"}
              aria-label={hasText ? "Edit variance explanation" : "Add variance explanation"}
              disabled={isSaving}
              onClick={() => setOpen(true)}
            >
              {hasText ? (
                <Pencil className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
              ) : (
                <MessageSquarePlus className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
              )}
            </button>
          ) : null}
        </div>
      </div>
      {modal}
    </>
  );
}

export function RevenuePage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const vcScrollDone = useRef(false);
  const [orgId, setOrgId] = useState<string>("");
  const [businessUnitId, setBusinessUnitId] = useState<string>("");
  const [divisionId, setDivisionId] = useState<string>("");
  const [matrixNote, setMatrixNote] = useState<string | null>(null);
  const [matrixHoverRow, setMatrixHoverRow] = useState<number | null>(null);
  const [matrixDensity, setMatrixDensity] = useState<"compact" | "comfortable">(() => {
    if (typeof window === "undefined") return "compact";
    const v = window.localStorage.getItem(MATRIX_DENSITY_KEY);
    return v === "comfortable" ? "comfortable" : "compact";
  });

  useEffect(() => {
    window.localStorage.setItem(MATRIX_DENSITY_KEY, matrixDensity);
  }, [matrixDensity]);

  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: async () => {
      const { data } = await api.get<OrgList>("/api/v1/organizations");
      return data;
    },
  });

  const firstOrg = orgs.data?.items[0]?.org_id;
  useEffect(() => {
    const fromUrl = searchParams.get("org_id");
    if (fromUrl) {
      setOrgId(fromUrl);
    }
  }, [searchParams]);

  useEffect(() => {
    if (searchParams.get("org_id")) return;
    if (firstOrg && !orgId) {
      setOrgId(firstOrg);
    }
  }, [firstOrg, orgId, searchParams]);

  useEffect(() => {
    vcScrollDone.current = false;
  }, [orgId]);

  useEffect(() => {
    setBusinessUnitId("");
    setDivisionId("");
  }, [orgId]);

  useEffect(() => {
    setDivisionId("");
  }, [businessUnitId]);

  const businessUnits = useQuery({
    queryKey: ["business-units", orgId],
    queryFn: async () => {
      const { data } = await api.get<{ items: BusinessUnitItem[] }>("/api/v1/business-units", {
        params: { org_id: orgId },
      });
      return data;
    },
    enabled: phase7 && Boolean(orgId),
  });

  const divisions = useQuery({
    queryKey: ["divisions", businessUnitId],
    queryFn: async () => {
      const { data } = await api.get<{ items: DivisionItem[] }>("/api/v1/divisions", {
        params: { business_unit_id: businessUnitId },
      });
      return data;
    },
    enabled: phase7 && Boolean(businessUnitId),
  });

  const matrix = useQuery({
    queryKey: ["revenue-matrix", orgId, businessUnitId, divisionId],
    queryFn: async () => {
      const params: Record<string, string> = { org_id: orgId };
      if (businessUnitId) params.business_unit_id = businessUnitId;
      if (businessUnitId && divisionId) params.division_id = divisionId;
      const { data } = await api.get<RevenueMatrixResponse>("/api/v1/revenue/matrix", { params });
      return data;
    },
    enabled: phase7 && Boolean(orgId),
  });

  useEffect(() => {
    if (!phase7 || !matrix.isSuccess || !matrix.data || vcScrollDone.current) return;
    const c = searchParams.get("vc_customer");
    const m = searchParams.get("vc_month");
    if (!c || !m) return;
    const key = `${c}:${m}`;
    const handle = window.setTimeout(() => {
      const el = document.querySelector(`[data-vc-focus="${key}"]`);
      if (el) {
        el.scrollIntoView({ block: "center", behavior: "smooth" });
        vcScrollDone.current = true;
        const next = new URLSearchParams(searchParams);
        next.delete("vc_customer");
        next.delete("vc_month");
        navigate({ pathname: "/revenue", search: next.toString() }, { replace: true });
      }
    }, 250);
    return () => window.clearTimeout(handle);
  }, [phase7, matrix.isSuccess, matrix.data, searchParams, navigate]);

  const saveMatrixCell = useMutation({
    mutationFn: async (payload: {
      org_id: string;
      customer_id: string;
      revenue_month: string;
      amount: string;
      business_unit_id: string | null;
      division_id: string | null;
    }) => {
      const { data } = await api.put<RevenueMatrixResponse>("/api/v1/revenue/matrix/cell", payload);
      return data;
    },
    onSuccess: () => {
      setMatrixNote(null);
      void queryClient.invalidateQueries({ queryKey: ["revenue-matrix", orgId, businessUnitId, divisionId] });
    },
    onError: () => {
      setMatrixNote("Could not save this cell. Check amount format and that your role may edit matrix values.");
    },
  });

  const saveVarianceComment = useMutation({
    mutationFn: async (payload: {
      org_id: string;
      customer_id: string;
      revenue_month: string;
      comment_text: string;
      business_unit_id: string | null;
      division_id: string | null;
    }) => {
      const { data } = await api.put<RevenueMatrixResponse>("/api/v1/revenue/matrix/variance-comment", payload);
      return data;
    },
    onSuccess: () => {
      setMatrixNote(null);
      void queryClient.invalidateQueries({ queryKey: ["revenue-matrix", orgId, businessUnitId, divisionId] });
      void queryClient.invalidateQueries({ queryKey: ["variance-comment-prompts"] });
    },
    onError: () => {
      setMatrixNote("Could not save variance narrative. Check permissions and length (max 4000 characters).");
    },
  });

  const revenue = useQuery({
    queryKey: ["revenue", orgId],
    queryFn: async () => {
      const params: Record<string, string> = { limit: "200" };
      if (orgId) params.org_id = orgId;
      const { data } = await api.get<RevenueListResponse>("/api/v1/revenue", { params });
      return data;
    },
    enabled:
      Boolean(orgId) &&
      (!phase7 || (matrix.isSuccess && matrix.data?.empty_reason === "no_customer_facts")),
  });

  const showMatrix =
    phase7 &&
    matrix.isSuccess &&
    matrix.data &&
    matrix.data.empty_reason !== "no_customer_facts" &&
    matrix.data.lines.length > 0;

  const showCustomerFactsDetail =
    Boolean(orgId) &&
    revenue.isSuccess &&
    (!phase7 || (matrix.isSuccess && matrix.data?.empty_reason === "no_customer_facts"));

  const matrixChartSeries = useMemo(() => {
    if (!matrix.data?.month_columns?.length || !matrix.data.lines.length) return [];
    const valueLines = matrix.data.lines.filter((l) => l.row_type === "value");
    const n = matrix.data.month_columns.length;
    const sums = new Array(n).fill(0);
    for (const line of valueLines) {
      line.amounts.forEach((a, i) => {
        if (i < n) sums[i] += parseAmountStr(a);
      });
    }
    return matrix.data.month_columns.map((c, i) => ({
      label: c.label,
      total: sums[i],
    }));
  }, [matrix.data]);

  const { series, totalAmount, dateMin, dateMax } = useMemo(() => {
    if (!revenue.data?.items.length) {
      return {
        series: [] as { date: string; total: number }[],
        totalAmount: 0,
        dateMin: null as string | null,
        dateMax: null as string | null,
      };
    }
    const map = new Map<string, number>();
    for (const row of revenue.data.items) {
      const a = parseAmountStr(row.amount);
      map.set(row.revenue_date, (map.get(row.revenue_date) ?? 0) + a);
    }
    const sorted = [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
    const tot = sorted.reduce((s, [, v]) => s + v, 0);
    return {
      series: sorted.map(([d, total]) => ({ date: d, total })),
      totalAmount: tot,
      dateMin: sorted[0]?.[0] ?? null,
      dateMax: sorted[sorted.length - 1]?.[0] ?? null,
    };
  }, [revenue.data]);

  const matrixTotal = useMemo(() => {
    if (!showMatrix || !matrix.data) return 0;
    return matrix.data.lines
      .filter((l) => l.row_type === "value")
      .flatMap((l) => l.amounts)
      .reduce((s, a) => s + parseAmountStr(a), 0);
  }, [showMatrix, matrix.data]);

  const matrixStyle = useMemo(() => {
    const compact = matrixDensity === "compact";
    /* Fixed row heights keep the split left/right tables pixel-aligned (independent row layout was drifting). */
    const rowHe = compact ? "h-9 min-h-[2.25rem] max-h-[2.25rem]" : "h-11 min-h-[2.75rem] max-h-[2.75rem]";
    return {
      compact,
      leftPane: compact ? "w-[19rem]" : "w-[26rem]",
      rowHe,
      thPad: compact ? "px-2" : "px-3",
      thText: compact ? "text-[10px] font-semibold tracking-tight" : "text-xs font-semibold",
      tdPad: compact ? "px-2" : "px-3",
      tdSr: compact ? "text-[11px] leading-none" : "text-xs leading-none",
      tdBody: compact ? "text-[11px] leading-none" : "text-[13px] leading-none",
      tdMono: compact ? "text-[11px] leading-none" : "text-[13px] leading-none",
      monthTh: compact ? "text-[10px] leading-none" : "text-[11px] leading-none",
    };
  }, [matrixDensity]);

  const chartTooltip = {
    contentStyle: {
      borderRadius: "12px",
      border: "1px solid #e2e8f0",
      boxShadow: "0 8px 24px rgba(15,23,42,0.08)",
    },
  };

  return (
    <div className="page-shell">
      <header className="page-header-block">
        <h1 className="page-headline">Revenue</h1>
        <p className="page-lede">
          {phase7 ? (
            <>
              Customer–month matrix matches the EUROPE workbook when facts include customers. Finance and delivery managers
              assigned to a customer can enter monthly totals at organization scope when spreadsheet import is not used
              (MoM change recalculates on the row below). Hover a change to add or edit an explanation; a teal dot means a note is saved. On touch, a faint icon stays visible—tap to edit.
              Optional BU and division narrow the grid for viewing; assigned DMs edit at organization scope only. Facts
              without a customer still appear in the detail table when the matrix is empty.
            </>
          ) : (
            <>
              Revenue facts for the selected organization. Enable Phase 7 on the API and{" "}
              <code className="rounded bg-neutral-100 px-1 py-0.5 font-mono text-[13px]">VITE_ENABLE_PHASE7=true</code>{" "}
              for the customer–month matrix and manual cell overrides.
            </>
          )}
        </p>
      </header>

      <div className="surface-card flex flex-wrap items-end gap-4 p-5">
        <div className="min-w-[220px]">
          <label className="form-field-label">Organization</label>
          <select
            className="input-modern !h-10 w-full"
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            disabled={orgs.isLoading}
          >
            <option value="">Select organization</option>
            {orgs.data?.items.map((o) => (
              <option key={o.org_id} value={o.org_id}>
                {o.org_name}
              </option>
            ))}
          </select>
        </div>
        {phase7 ? (
          <>
            <div className="min-w-[200px]">
              <label className="form-field-label">Business unit</label>
              <select
                className="input-modern !h-10 w-full"
                value={businessUnitId}
                onChange={(e) => setBusinessUnitId(e.target.value)}
                disabled={!orgId || businessUnits.isLoading}
              >
                <option value="">All (organization total)</option>
                {businessUnits.data?.items.map((b) => (
                  <option key={b.business_unit_id} value={b.business_unit_id}>
                    {b.business_unit_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-[200px]">
              <label className="form-field-label">Division</label>
              <select
                className="input-modern !h-10 w-full"
                value={divisionId}
                onChange={(e) => setDivisionId(e.target.value)}
                disabled={!businessUnitId || divisions.isLoading}
              >
                <option value="">All in BU</option>
                {divisions.data?.items.map((d) => (
                  <option key={d.division_id} value={d.division_id}>
                    {d.division_name}
                  </option>
                ))}
              </select>
            </div>
          </>
        ) : null}
      </div>

      {phase7 && matrix.isError ? (
        <div
          className="rounded-xl border border-red-200 bg-red-50/90 px-4 py-3 text-sm text-red-800 shadow-sm"
          role="alert"
        >
          Could not load revenue matrix.{" "}
          {matrix.error instanceof Error ? matrix.error.message : "Check the API and your session."}
        </div>
      ) : null}

      {matrixNote ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-950 shadow-sm" role="status">
          {matrixNote}
        </div>
      ) : null}

      {!orgId && !orgs.isLoading ? (
        <div className="surface-card border-dashed px-6 py-14 text-center text-sm text-ink-muted">
          Select an organization to load revenue. If the list is empty, ask an admin to assign org access.
        </div>
      ) : null}

      {phase7 && orgId && matrix.isLoading ? <p className="text-sm font-medium text-ink-muted">Loading…</p> : null}

      {orgId && showMatrix && matrix.data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Total (matrix)</p>
              <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-ink">
                {matrixTotal.toLocaleString(undefined, { maximumFractionDigits: 2 })}{" "}
                <span className="text-base font-normal text-ink-muted">{matrix.data.currency_code}</span>
              </p>
            </div>
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Customers</p>
              <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-ink">
                {matrix.data.lines.filter((l) => l.row_type === "value").length}
              </p>
            </div>
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Month columns</p>
              <p className="mt-2 text-sm font-medium text-ink">{matrix.data.month_columns.length}</p>
            </div>
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Matrix scope</p>
              <p className="mt-2 text-sm text-ink">
                {matrix.data.matrix_scope === "division"
                  ? "Division"
                  : matrix.data.matrix_scope === "business_unit"
                    ? "Business unit"
                    : "Organization"}
              </p>
            </div>
          </div>

          {matrixChartSeries.length > 0 ? (
            <div className="surface-card p-6">
              <h2 className="text-sm font-semibold text-ink">Total by month (matrix)</h2>
              <p className="mt-1 text-xs text-ink-muted">Sum of value rows per month column.</p>
              <div className="mt-4 h-[280px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={matrixChartSeries} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="revMatrixArea" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#14b8a6" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#14b8a6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748b" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) =>
                        v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}k` : String(v)
                      }
                    />
                    <Tooltip
                      {...chartTooltip}
                      formatter={(value: number) => [value.toLocaleString(undefined, { maximumFractionDigits: 2 }), "Total"]}
                      labelFormatter={(l) => String(l)}
                    />
                    <Area type="monotone" dataKey="total" stroke="#0d9488" strokeWidth={2} fill="url(#revMatrixArea)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : null}

          <div className="space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-heading text-[16px]">Customer–month matrix</h2>
                <p className="mt-0.5 max-w-xl text-xs text-ink-muted">
                  Frozen row labels in the left pane; only months scroll on the right — nothing slides under the label
                  columns. Use density to fit more months on screen.
                </p>
              </div>
              <div
                className="inline-flex shrink-0 rounded-xl border border-black/[0.08] bg-neutral-50/90 p-0.5 shadow-sm"
                role="group"
                aria-label="Matrix row density"
              >
                <button
                  type="button"
                  className={`rounded-lg px-3 py-2 text-[13px] font-medium transition-colors ${
                    matrixDensity === "compact"
                      ? "bg-white text-ink shadow-sm"
                      : "text-ink-muted hover:text-ink"
                  }`}
                  onClick={() => setMatrixDensity("compact")}
                >
                  Compact
                </button>
                <button
                  type="button"
                  className={`rounded-lg px-3 py-2 text-[13px] font-medium transition-colors ${
                    matrixDensity === "comfortable"
                      ? "bg-white text-ink shadow-sm"
                      : "text-ink-muted hover:text-ink"
                  }`}
                  onClick={() => setMatrixDensity("comfortable")}
                >
                  Comfortable
                </button>
              </div>
            </div>

            <div
              className="flex max-w-full overflow-hidden rounded-2xl border border-border/60 bg-white shadow-card"
              onMouseLeave={() => setMatrixHoverRow(null)}
            >
              <div
                className={`shrink-0 border-r border-neutral-200 bg-neutral-100 shadow-[6px_0_16px_-8px_rgba(0,0,0,0.15)] ${matrixStyle.leftPane}`}
              >
                <table className="w-full table-fixed border-collapse text-sm">
                  <colgroup>
                    <col className={matrixStyle.compact ? "w-[2.75rem]" : "w-[4rem]"} />
                    <col className={matrixStyle.compact ? "w-[9rem]" : "w-[11rem]"} />
                    <col />
                  </colgroup>
                  <thead className="sticky top-0 z-20 bg-neutral-100">
                    <tr>
                      <th
                        className={`${matrixStyle.thPad} ${matrixStyle.rowHe} align-middle overflow-hidden border-b border-border text-left ${matrixStyle.thText} text-ink`}
                        scope="col"
                      >
                        Sr.
                      </th>
                      <th
                        className={`${matrixStyle.thPad} ${matrixStyle.rowHe} align-middle overflow-hidden border-b border-border text-left ${matrixStyle.thText} text-ink`}
                        scope="col"
                      >
                        Customer (legal)
                      </th>
                      <th
                        className={`${matrixStyle.thPad} ${matrixStyle.rowHe} align-middle overflow-hidden border-b border-border text-left ${matrixStyle.thText} text-ink`}
                        scope="col"
                      >
                        Common
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {matrix.data.lines.map((line, idx) => {
                      const isDelta = line.row_type === "delta";
                      const rowBg = isDelta
                        ? "bg-neutral-50"
                        : matrixHoverRow === idx
                          ? "bg-teal-50/55"
                          : "bg-white";
                      return (
                        <tr
                          key={`matrix-left-${line.row_type}-${idx}`}
                          className={isDelta ? "text-ink-muted" : "text-ink"}
                          onMouseEnter={() => setMatrixHoverRow(idx)}
                        >
                          <td
                            className={`${matrixStyle.tdPad} ${matrixStyle.rowHe} align-middle overflow-hidden border-b border-border font-mono tabular-nums ${matrixStyle.tdSr} ${rowBg}`}
                          >
                            {line.sr_no != null ? line.sr_no : ""}
                          </td>
                          <td
                            className={`${matrixStyle.tdPad} ${matrixStyle.rowHe} max-w-0 truncate align-middle overflow-hidden border-b border-border font-medium text-ink ${matrixStyle.tdBody} ${rowBg}`}
                            title={line.customer_legal}
                          >
                            {line.customer_legal}
                          </td>
                          <td
                            className={`${matrixStyle.tdPad} ${matrixStyle.rowHe} max-w-0 truncate align-middle overflow-hidden border-b border-border ${matrixStyle.tdBody} text-ink-muted ${rowBg}`}
                            title={line.customer_common ?? ""}
                          >
                            {line.customer_common ?? ""}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div
                className="min-w-0 flex-1 overflow-x-auto overscroll-x-contain"
                role="region"
                aria-label="Revenue amounts by month"
              >
                <table className="min-w-max border-collapse text-sm">
                  <thead className="sticky top-0 z-10 bg-neutral-100">
                    <tr>
                      {matrix.data.month_columns.map((c, j) => (
                        <th
                          key={c.key}
                          scope="col"
                          className={`${matrixStyle.thPad} ${matrixStyle.rowHe} align-middle overflow-hidden whitespace-nowrap border-b border-border text-right font-mono font-semibold text-ink ${matrixStyle.monthTh}`}
                        >
                          {phase7 && j > 0 ? (
                            <div className="flex w-full min-w-0 items-center">
                              <span className="min-w-0 flex-1 text-right">{c.label}</span>
                              <span className="w-7 shrink-0" aria-hidden />
                            </div>
                          ) : (
                            c.label
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {matrix.data.lines.map((line, idx) => {
                      const isDelta = line.row_type === "delta";
                      const rowBg = isDelta
                        ? "bg-neutral-50"
                        : matrixHoverRow === idx
                          ? "bg-teal-50/55"
                          : "bg-white";
                      return (
                        <tr
                          key={`matrix-right-${line.row_type}-${idx}`}
                          className={isDelta ? "text-ink-muted" : "text-ink"}
                          onMouseEnter={() => setMatrixHoverRow(idx)}
                        >
                          {line.amounts.map((cell, j) => {
                            const narrativeCell =
                              isDelta && j > 0 && Boolean(line.customer_id);
                            const monthGutter = phase7 && j > 0;
                            const varianceRowBlock =
                              isDelta &&
                              cell !== "" &&
                              j > 0 &&
                              Boolean(line.customer_id);

                            const cellBody = isDelta ? (
                              cell === "" ? null : j > 0 && line.customer_id ? (
                                <VarianceNarrativeBlock
                                  narrative={line.variance_comments?.[j]}
                                  editable={line.variance_comments_editable === true}
                                  focusKey={`${line.customer_id}:${matrix.data!.month_columns[j].key}`}
                                  isSaving={saveVarianceComment.isPending}
                                  onSave={async (text) => {
                                    await saveVarianceComment.mutateAsync({
                                      org_id: orgId,
                                      customer_id: line.customer_id!,
                                      revenue_month: matrix.data!.month_columns[j].key,
                                      comment_text: text,
                                      business_unit_id: businessUnitId || null,
                                      division_id: businessUnitId ? divisionId || null : null,
                                    });
                                  }}
                                >
                                  <MomDeltaCell value={cell} />
                                </VarianceNarrativeBlock>
                              ) : (
                                <MomDeltaCell value={cell} />
                              )
                            ) : line.customer_id && matrix.data!.month_columns[j] ? (
                              <MatrixAmountInput
                                amount={cell}
                                compact={matrixStyle.compact}
                                disabled={saveMatrixCell.isPending || line.amounts_editable === false}
                                onCommit={(next) => {
                                  setMatrixNote(null);
                                  saveMatrixCell.mutate({
                                    org_id: orgId,
                                    customer_id: line.customer_id!,
                                    revenue_month: matrix.data!.month_columns[j].key,
                                    amount: next,
                                    business_unit_id: businessUnitId || null,
                                    division_id: businessUnitId ? divisionId || null : null,
                                  });
                                }}
                              />
                            ) : (
                              cell
                            );

                            return (
                              <td
                                key={j}
                                className={`${matrixStyle.tdPad} ${matrixStyle.rowHe} align-middle whitespace-nowrap border-b border-border text-right font-mono tabular-nums ${matrixStyle.tdMono} ${rowBg} ${
                                  isDelta ? "text-ink-muted" : "text-ink"
                                } ${narrativeCell ? "group/vc overflow-visible" : "overflow-hidden"}`}
                              >
                                {monthGutter && !varianceRowBlock ? (
                                  <div className="flex w-full min-w-0 items-center">
                                    <div className="min-w-0 flex-1 overflow-hidden">{cellBody}</div>
                                    <div className="w-7 shrink-0" aria-hidden />
                                  </div>
                                ) : (
                                  cellBody
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      ) : null}

      {phase7 && orgId && matrix.isSuccess && matrix.data?.empty_reason === "no_customer_facts" ? (
        <p className="text-sm text-ink-muted">
          No customer-scoped facts for this organization yet — showing raw fact rows only. Import a EUROPE workbook or
          ensure facts include a customer.
        </p>
      ) : null}

      {orgId && revenue.isFetching ? (
        <p className="text-sm font-medium text-ink-muted">Loading detail rows…</p>
      ) : null}

      {showCustomerFactsDetail ? (
        <>
          {series.length > 0 ? (
            <div className="surface-card p-6">
              <h2 className="text-sm font-semibold text-ink">Daily total (all facts on this page)</h2>
              <div className="mt-4 h-[240px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="revArea" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#14b8a6" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#14b8a6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748b" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) =>
                        v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}k` : String(v)
                      }
                    />
                    <Tooltip
                      {...chartTooltip}
                      formatter={(value: number) => [value.toLocaleString(undefined, { maximumFractionDigits: 2 }), "Total"]}
                    />
                    <Area type="monotone" dataKey="total" stroke="#0d9488" strokeWidth={2} fill="url(#revArea)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Total (loaded page)</p>
              <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-ink">
                {totalAmount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </p>
            </div>
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Rows in view</p>
              <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-ink">{revenue.data?.items.length ?? 0}</p>
            </div>
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Date span</p>
              <p className="mt-2 text-sm font-medium text-ink">
                {dateMin && dateMax ? (
                  <>
                    {dateMin} <span className="text-ink-muted">→</span> {dateMax}
                  </>
                ) : (
                  "—"
                )}
              </p>
            </div>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-border/60 bg-white shadow-card">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-surface-subtle/80 text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <tr>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3">CCY</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="hidden px-4 py-3 md:table-cell">Batch</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(revenue.data?.items ?? []).map((row) => (
                  <tr key={row.revenue_id} className="transition-colors hover:bg-teal-50/40">
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-sm text-ink">{row.revenue_date}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-sm text-ink">{row.amount}</td>
                    <td className="px-4 py-3 text-ink-muted">{row.currency_code}</td>
                    <td className="px-4 py-3 text-ink">{row.source_system}</td>
                    <td className="hidden px-4 py-3 font-mono text-xs text-ink-muted md:table-cell">
                      {row.batch_id ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {orgId &&
      revenue.isSuccess &&
      revenue.data.items.length === 0 &&
      (!phase7 || (matrix.isSuccess && matrix.data?.empty_reason === "no_customer_facts")) ? (
        <div className="surface-card px-6 py-14 text-center text-sm text-ink-muted">
          No revenue rows for this organization yet. Import an Excel file on the Import page.
        </div>
      ) : null}
    </div>
  );
}
