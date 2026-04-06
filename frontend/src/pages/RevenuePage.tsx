import { useQuery } from "@tanstack/react-query";
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
  const n = parseFloat(v.replace(/,/g, ""));
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

export function RevenuePage() {
  const [orgId, setOrgId] = useState<string>("");

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

  const revenue = useQuery({
    queryKey: ["revenue", orgId],
    queryFn: async () => {
      const params: Record<string, string> = { limit: "100" };
      if (orgId) params.org_id = orgId;
      const { data } = await api.get<RevenueListResponse>("/api/v1/revenue", { params });
      return data;
    },
    enabled: Boolean(orgId),
  });

  const { series, totalAmount, dateMin, dateMax } = useMemo(() => {
    if (!revenue.data?.items.length) {
      return { series: [] as { date: string; total: number }[], totalAmount: 0, dateMin: null as string | null, dateMax: null as string | null };
    }
    const map = new Map<string, number>();
    for (const row of revenue.data.items) {
      const a = parseAmountStr(row.amount);
      map.set(row.revenue_date, (map.get(row.revenue_date) ?? 0) + a);
    }
    const sorted = [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
    const totalAmount = sorted.reduce((s, [, v]) => s + v, 0);
    return {
      series: sorted.map(([date, total]) => ({ date, total })),
      totalAmount,
      dateMin: sorted[0]?.[0] ?? null,
      dateMax: sorted[sorted.length - 1]?.[0] ?? null,
    };
  }, [revenue.data]);

  const chartTooltip = {
    contentStyle: {
      borderRadius: "12px",
      border: "1px solid #e2e8f0",
      boxShadow: "0 8px 24px rgba(15,23,42,0.08)",
    },
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-8">
      <header className="relative overflow-hidden rounded-2xl border border-border/80 bg-gradient-to-br from-white via-white to-teal-50/30 p-8 shadow-card">
        <div className="pointer-events-none absolute -right-12 top-0 h-40 w-40 rounded-full bg-primary/10 blur-3xl" aria-hidden />
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Fact table</p>
        <h1 className="text-display mt-2 text-3xl">Revenue</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
          Imported facts from <code className="rounded-md bg-surface-subtle px-1.5 py-0.5 font-mono text-xs text-ink">fact_revenue</code> for your
          organization scope (up to 100 rows per request).
        </p>
      </header>

      <div className="surface-card flex flex-wrap items-end gap-4 p-5">
        <div className="min-w-[220px]">
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Organization</label>
          <select
            className="input-modern h-10 w-full"
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
      </div>

      {revenue.isError ? (
        <div
          className="rounded-xl border border-red-200 bg-red-50/90 px-4 py-3 text-sm text-red-800 shadow-sm"
          role="alert"
        >
          Could not load revenue.{" "}
          {revenue.error instanceof Error ? revenue.error.message : "Check the API and your session."}
        </div>
      ) : null}

      {!orgId && !orgs.isLoading ? (
        <div className="surface-card border-dashed px-6 py-14 text-center text-sm text-ink-muted">
          Select an organization to load revenue rows. If the list is empty, register or ask an admin to assign org
          access.
        </div>
      ) : null}

      {orgId && revenue.isSuccess && revenue.data.items.length === 0 ? (
        <div className="surface-card px-6 py-14 text-center text-sm text-ink-muted">
          No revenue rows for this organization yet. Import an Excel file on the Import page, then return here.
        </div>
      ) : null}

      {orgId && revenue.isLoading ? (
        <p className="text-sm font-medium text-ink-muted">Loading…</p>
      ) : null}

      {orgId && revenue.isSuccess && revenue.data.items.length > 0 ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Total (loaded page)</p>
              <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-ink">
                {totalAmount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </p>
            </div>
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Rows in view</p>
              <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-ink">{revenue.data.items.length}</p>
            </div>
            <div className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Date span (aggregated)</p>
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

          {series.length > 0 ? (
            <div className="surface-card p-6">
              <h2 className="text-sm font-semibold text-ink">Daily total (this page)</h2>
              <p className="mt-1 text-xs text-ink-muted">Amounts summed by calendar date for the rows currently loaded.</p>
              <div className="mt-4 h-[280px] w-full">
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
                      labelFormatter={(l) => String(l)}
                    />
                    <Area type="monotone" dataKey="total" stroke="#0d9488" strokeWidth={2} fill="url(#revArea)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : null}

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
                {revenue.data.items.map((row) => (
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
            {revenue.data.next_cursor ? (
              <p className="border-t border-border px-4 py-2 text-xs text-ink-muted">
                More rows available — pagination via API cursor not yet wired in this view.
              </p>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
