import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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

function MatrixAmountInput({
  amount,
  disabled,
  onCommit,
}: {
  amount: string;
  disabled?: boolean;
  onCommit: (next: string) => void;
}) {
  const [v, setV] = useState(amount);
  useEffect(() => setV(amount), [amount]);
  return (
    <input
      type="text"
      inputMode="decimal"
      className="w-full min-w-[5.5rem] rounded border border-transparent bg-transparent px-1 py-0.5 text-right font-mono text-[13px] tabular-nums text-ink hover:border-black/[0.08] focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25"
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
      className={`inline-flex items-center justify-end gap-1 font-mono tabular-nums ${
        pos ? "text-emerald-700" : "text-red-700"
      }`}
    >
      {pos ? <ArrowUp className="h-3.5 w-3.5 shrink-0" aria-hidden /> : <ArrowDown className="h-3.5 w-3.5 shrink-0" aria-hidden />}
      {value}
    </span>
  );
}

export function RevenuePage() {
  const queryClient = useQueryClient();
  const [orgId, setOrgId] = useState<string>("");
  const [businessUnitId, setBusinessUnitId] = useState<string>("");
  const [divisionId, setDivisionId] = useState<string>("");
  const [matrixNote, setMatrixNote] = useState<string | null>(null);

  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: async () => {
      const { data } = await api.get<OrgList>("/api/v1/organizations");
      return data;
    },
  });

  const firstOrg = orgs.data?.items[0]?.org_id;
  useEffect(() => {
    if (firstOrg && !orgId) {
      setOrgId(firstOrg);
    }
  }, [firstOrg, orgId]);

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
    enabled: Boolean(orgId),
  });

  const divisions = useQuery({
    queryKey: ["divisions", businessUnitId],
    queryFn: async () => {
      const { data } = await api.get<{ items: DivisionItem[] }>("/api/v1/divisions", {
        params: { business_unit_id: businessUnitId },
      });
      return data;
    },
    enabled: Boolean(businessUnitId),
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
    enabled: Boolean(orgId),
  });

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

  const revenue = useQuery({
    queryKey: ["revenue", orgId],
    queryFn: async () => {
      const params: Record<string, string> = { limit: "200" };
      if (orgId) params.org_id = orgId;
      const { data } = await api.get<RevenueListResponse>("/api/v1/revenue", { params });
      return data;
    },
    enabled: Boolean(orgId) && matrix.isSuccess && matrix.data?.empty_reason === "no_customer_facts",
  });

  const showMatrix =
    matrix.isSuccess &&
    matrix.data &&
    matrix.data.empty_reason !== "no_customer_facts" &&
    matrix.data.lines.length > 0;

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

  const chartTooltip = {
    contentStyle: {
      borderRadius: "12px",
      border: "1px solid #e2e8f0",
      boxShadow: "0 8px 24px rgba(15,23,42,0.08)",
    },
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-10">
      <header className="border-b border-black/[0.06] pb-8">
        <h1 className="page-headline">Revenue</h1>
        <p className="page-lede">
          Customer–month matrix matches the EUROPE workbook when facts include customers. Value rows are editable to fix
          imports or enter monthly totals (MoM change recalculates below). Optional BU and division narrow the grid. Facts
          without a customer still appear in the detail table when the matrix is empty.
        </p>
      </header>

      <div className="surface-card flex flex-wrap items-end gap-4 p-5">
        <div className="min-w-[220px]">
          <label className="small-caps-label mb-1.5 block">Organization</label>
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
        <div className="min-w-[200px]">
          <label className="small-caps-label mb-1.5 block">Business unit</label>
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
          <label className="small-caps-label mb-1.5 block">Division</label>
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
      </div>

      {matrix.isError ? (
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

      {orgId && matrix.isLoading ? <p className="text-sm font-medium text-ink-muted">Loading…</p> : null}

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

          <div className="overflow-x-auto rounded-2xl border border-border/60 bg-white shadow-card">
            <table className="min-w-max divide-y divide-border text-sm">
              <thead className="sticky top-0 z-10 bg-surface-subtle/95 text-left text-xs font-semibold text-ink">
                <tr>
                  <th className="sticky left-0 z-20 border-b border-border bg-surface-subtle px-3 py-3 font-medium">
                    Sr. No.
                  </th>
                  <th className="sticky left-[4.5rem] z-20 border-b border-border bg-surface-subtle px-3 py-3 font-medium shadow-[2px_0_8px_rgba(0,0,0,0.04)]">
                    Customer Name
                  </th>
                  <th className="sticky left-[14rem] z-20 border-b border-border bg-surface-subtle px-3 py-3 font-medium shadow-[2px_0_8px_rgba(0,0,0,0.04)]">
                    Customer Name
                  </th>
                  {matrix.data.month_columns.map((c) => (
                    <th
                      key={c.key}
                      className="whitespace-nowrap border-b border-border px-2 py-3 text-right font-mono text-[11px] font-medium tracking-tight text-ink"
                    >
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {matrix.data.lines.map((line, idx) => (
                  <tr
                    key={`${line.row_type}-${idx}`}
                    className={
                      line.row_type === "delta"
                        ? "bg-neutral-50/90 text-ink-muted"
                        : "transition-colors hover:bg-teal-50/30"
                    }
                  >
                    <td className="sticky left-0 z-10 whitespace-nowrap border-b border-border bg-white px-3 py-2 font-mono text-xs text-ink">
                      {line.sr_no != null ? line.sr_no : ""}
                    </td>
                    <td className="sticky left-[4.5rem] z-10 max-w-[10rem] border-b border-border bg-white px-3 py-2 text-[13px] text-ink shadow-[2px_0_8px_rgba(0,0,0,0.04)]">
                      {line.customer_legal}
                    </td>
                    <td className="sticky left-[14rem] z-10 max-w-[8rem] border-b border-border bg-white px-3 py-2 text-[13px] text-ink-muted shadow-[2px_0_8px_rgba(0,0,0,0.04)]">
                      {line.customer_common ?? ""}
                    </td>
                    {line.amounts.map((cell, j) => (
                      <td
                        key={j}
                        className={`whitespace-nowrap border-b border-border px-2 py-2 text-right font-mono text-[13px] tabular-nums ${
                          line.row_type === "delta" ? "text-ink-muted" : "text-ink"
                        }`}
                      >
                        {line.row_type === "delta" ? (
                          cell === "" ? null : <MomDeltaCell value={cell} />
                        ) : line.customer_id && matrix.data.month_columns[j] ? (
                          <MatrixAmountInput
                            amount={cell}
                            disabled={saveMatrixCell.isPending}
                            onCommit={(next) => {
                              setMatrixNote(null);
                              saveMatrixCell.mutate({
                                org_id: orgId,
                                customer_id: line.customer_id!,
                                revenue_month: matrix.data.month_columns[j].key,
                                amount: next,
                                business_unit_id: businessUnitId || null,
                                division_id: businessUnitId ? divisionId || null : null,
                              });
                            }}
                          />
                        ) : (
                          cell
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {orgId && matrix.isSuccess && matrix.data?.empty_reason === "no_customer_facts" ? (
        <p className="text-sm text-ink-muted">
          No customer-scoped facts for this organization yet — showing raw fact rows only. Import a EUROPE workbook or
          ensure facts include a customer.
        </p>
      ) : null}

      {orgId && revenue.isFetching ? (
        <p className="text-sm font-medium text-ink-muted">Loading detail rows…</p>
      ) : null}

      {orgId && matrix.isSuccess && matrix.data?.empty_reason === "no_customer_facts" && revenue.isSuccess ? (
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
      matrix.isSuccess &&
      matrix.data?.empty_reason === "no_customer_facts" &&
      revenue.isSuccess &&
      revenue.data.items.length === 0 ? (
        <div className="surface-card px-6 py-14 text-center text-sm text-ink-muted">
          No revenue rows for this organization yet. Import an Excel file on the Import page.
        </div>
      ) : null}
    </div>
  );
}
