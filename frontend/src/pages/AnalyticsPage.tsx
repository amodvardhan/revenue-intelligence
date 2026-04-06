import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/services/api";

function parseAmount(v: unknown): number {
  if (v == null) return 0;
  const n = parseFloat(String(v).replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

function rowLabel(row: Record<string, unknown>): string {
  return String(
    row.division_name ?? row.business_unit_name ?? row.org_name ?? "—",
  );
}

interface OrgList {
  items: Array<{ org_id: string; org_name: string }>;
}

type Hierarchy = "org" | "bu" | "division";
type CompareKind = "mom" | "qoq" | "yoy";

export function AnalyticsPage() {
  const [orgId, setOrgId] = useState<string>("");
  const [hierarchy, setHierarchy] = useState<Hierarchy>("org");
  const [from, setFrom] = useState("2026-01-01");
  const [to, setTo] = useState("2026-03-31");

  const [compareKind, setCompareKind] = useState<CompareKind>("yoy");
  const [curFrom, setCurFrom] = useState("2026-01-01");
  const [curTo, setCurTo] = useState("2026-03-31");
  const [cmpFrom, setCmpFrom] = useState("2025-01-01");
  const [cmpTo, setCmpTo] = useState("2025-03-31");

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

  const rollup = useQuery({
    queryKey: ["analytics-rollup", orgId, hierarchy, from, to],
    queryFn: async () => {
      const { data } = await api.get("/api/v1/analytics/revenue/rollup", {
        params: {
          hierarchy,
          revenue_date_from: from,
          revenue_date_to: to,
          org_id: orgId,
        },
      });
      return data as {
        rows: Record<string, unknown>[];
        as_of: string;
        hierarchy: string;
      };
    },
    enabled: Boolean(orgId),
  });

  const compare = useQuery({
    queryKey: ["analytics-compare", orgId, hierarchy, compareKind, curFrom, curTo, cmpFrom, cmpTo],
    queryFn: async () => {
      const { data } = await api.get("/api/v1/analytics/revenue/compare", {
        params: {
          hierarchy,
          compare: compareKind,
          current_period_from: curFrom,
          current_period_to: curTo,
          comparison_period_from: cmpFrom,
          comparison_period_to: cmpTo,
          org_id: orgId,
        },
      });
      return data as {
        rows: Record<string, unknown>[];
        current_period: { from: string; to: string; label: string };
        comparison_period: { from: string; to: string; label: string };
        as_of: string;
      };
    },
    enabled: Boolean(orgId),
  });

  const rollupChartData = useMemo(() => {
    if (!rollup.data?.rows?.length) return [];
    return rollup.data.rows.map((row, i) => ({
      id: String(i),
      name: rowLabel(row).length > 36 ? `${rowLabel(row).slice(0, 34)}…` : rowLabel(row),
      revenue: parseAmount(row.revenue),
    }));
  }, [rollup.data]);

  const compareChartData = useMemo(() => {
    if (!compare.data?.rows?.length) return [];
    return compare.data.rows.map((row, i) => ({
      id: String(i),
      name: rowLabel(row).length > 28 ? `${rowLabel(row).slice(0, 26)}…` : rowLabel(row),
      current: row.current_missing ? 0 : parseAmount(row.current_revenue),
      baseline: row.comparison_missing ? 0 : parseAmount(row.comparison_revenue),
      currentMissing: Boolean(row.current_missing),
      baselineMissing: Boolean(row.comparison_missing),
    }));
  }, [compare.data]);

  const freshness = useQuery({
    queryKey: ["analytics-freshness"],
    queryFn: async () => {
      const { data } = await api.get("/api/v1/analytics/freshness");
      return data as {
        structures: Array<{
          structure_name: string;
          last_refresh_completed_at: string | null;
          last_completed_batch_id: string | null;
        }>;
        notes: string;
      };
    },
  });

  const chartTooltip = {
    contentStyle: {
      borderRadius: "12px",
      border: "1px solid #e2e8f0",
      boxShadow: "0 8px 24px rgba(15,23,42,0.08)",
    },
    labelStyle: { fontWeight: 600, color: "#0f172a" },
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-8">
      <header className="relative overflow-hidden rounded-2xl border border-border/80 bg-gradient-to-br from-white via-white to-cyan-50/40 p-8 shadow-card">
        <div
          className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-primary/10 blur-3xl"
          aria-hidden
        />
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Analytics workspace</p>
        <h1 className="text-display mt-2 text-3xl">Analytics</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
          Hierarchical rollups and period-over-period comparisons. Totals use the same underlying facts as the{" "}
          <Link to="/revenue" className="font-semibold text-primary underline-offset-2 hover:underline">
            Revenue
          </Link>{" "}
          view when you use the same organization and filters.
        </p>
      </header>

      <p className="rounded-xl border border-cyan-200/50 bg-cyan-50/40 px-4 py-3 text-xs leading-relaxed text-ink">
        <strong className="font-semibold text-ink">Explicit periods only.</strong> All ranges use the date fields below —
        there are no presets such as &quot;last quarter&quot; without showing the exact from/to dates (Story 2.2).
      </p>

      <div className="surface-card flex flex-wrap items-end gap-4 p-5">
        <div className="min-w-[220px]">
          <label htmlFor="analytics-org" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Organization
          </label>
          <select
            id="analytics-org"
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
        <div>
          <label htmlFor="analytics-hierarchy" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Hierarchy
          </label>
          <select
            id="analytics-hierarchy"
            className="input-modern h-10"
            value={hierarchy}
            onChange={(e) => setHierarchy(e.target.value as Hierarchy)}
          >
            <option value="org">Organization</option>
            <option value="bu">Business unit</option>
            <option value="division">Division</option>
          </select>
        </div>
        <div>
          <label htmlFor="analytics-from" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Rollup from
          </label>
          <input
            id="analytics-from"
            type="date"
            className="input-modern h-10"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="analytics-to" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Rollup to
          </label>
          <input
            id="analytics-to"
            type="date"
            className="input-modern h-10"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
      </div>

      <section className="surface-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-ink">Rollup</h2>
            <p className="mt-1 max-w-xl text-xs text-ink-muted">
              Drill-down: open{" "}
              <Link to="/revenue" className="font-medium text-primary underline-offset-2 hover:underline">
                Revenue
              </Link>{" "}
              and apply the same organization and date range to reconcile row-level facts.
            </p>
          </div>
        </div>
        {rollup.isError ? (
          <p className="mt-4 text-sm text-red-700">Could not load rollup.</p>
        ) : null}
        {rollup.data ? (
          <div className="mt-5 space-y-4">
            <p className="text-xs font-medium text-ink-muted">
              As of {rollup.data.as_of} · grain {rollup.data.hierarchy}
            </p>
            {rollupChartData.length > 0 ? (
              <div className="h-[min(420px,50vh)] w-full min-h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rollupChartData} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="rollupGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#14b8a6" />
                        <stop offset="100%" stopColor="#0d9488" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748b" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}k` : String(v))}
                    />
                    <Tooltip
                      {...chartTooltip}
                      formatter={(value: number) => [value.toLocaleString(undefined, { maximumFractionDigits: 2 }), "Revenue"]}
                    />
                    <Bar dataKey="revenue" fill="url(#rollupGrad)" radius={[6, 6, 0, 0]} maxBarSize={48} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : null}
            <div className="overflow-x-auto rounded-xl border border-border/60 bg-surface-subtle/50">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    <th className="py-3 pl-4 pr-4">Name</th>
                    <th className="py-3 pr-4 text-right">Revenue</th>
                    <th className="py-3 pr-4 text-right">Child count</th>
                  </tr>
                </thead>
                <tbody>
                  {rollup.data.rows.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="py-6 text-center text-sm text-slate-600">
                        No revenue in this date range for the selected filters.
                      </td>
                    </tr>
                  ) : (
                    rollup.data.rows.map((row, i) => (
                      <tr key={i} className="border-b border-slate-100/80 transition-colors hover:bg-white/80">
                        <td className="py-2.5 pl-4 pr-4 text-ink">
                          {(row.division_name as string) ||
                            (row.business_unit_name as string) ||
                            (row.org_name as string)}
                        </td>
                        <td className="py-2.5 pr-4 text-right font-mono text-sm tabular-nums text-ink">
                          {row.revenue as string}
                        </td>
                        <td className="py-2.5 pr-4 text-right text-ink-muted">{String(row.child_count ?? "")}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">{rollup.isLoading ? "Loading…" : "Select an organization."}</p>
        )}
      </section>

      <section className="surface-card p-6">
        <h2 className="text-lg font-semibold text-ink">Compare</h2>
        <p className="mt-1 max-w-2xl text-xs text-ink-muted">
          MoM / QoQ / YoY labels describe the comparison style; the numbers always use the <strong className="text-ink">exact</strong>{" "}
          current and baseline date ranges you set (not ambiguous rolling windows).
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="analytics-compare-kind" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Compare style
            </label>
            <select
              id="analytics-compare-kind"
              className="input-modern h-9"
              value={compareKind}
              onChange={(e) => setCompareKind(e.target.value as CompareKind)}
            >
              <option value="mom">MoM</option>
              <option value="qoq">QoQ</option>
              <option value="yoy">YoY</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Current from / to</label>
            <div className="flex gap-1">
              <input
                type="date"
                className="input-modern h-9"
                value={curFrom}
                onChange={(e) => setCurFrom(e.target.value)}
              />
              <input
                type="date"
                className="input-modern h-9"
                value={curTo}
                onChange={(e) => setCurTo(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Baseline from / to</label>
            <div className="flex gap-1">
              <input
                type="date"
                className="input-modern h-9"
                value={cmpFrom}
                onChange={(e) => setCmpFrom(e.target.value)}
              />
              <input
                type="date"
                className="input-modern h-9"
                value={cmpTo}
                onChange={(e) => setCmpTo(e.target.value)}
              />
            </div>
          </div>
        </div>
        {compare.isError ? (
          <p className="mt-2 text-sm text-red-700">Could not load comparison.</p>
        ) : null}
        {compare.data ? (
          <div className="mt-4 space-y-4">
            <p className="text-xs font-medium text-ink-muted">
              Current: {compare.data.current_period.label} · Baseline: {compare.data.comparison_period.label} · As of{" "}
              {compare.data.as_of}
            </p>
            {compareChartData.length > 0 ? (
              <div>
                <div className="h-[min(380px,45vh)] w-full min-h-[220px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={compareChartData} margin={{ top: 8, right: 8, left: 4, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                      <XAxis
                        dataKey="name"
                        tick={{ fontSize: 10, fill: "#64748b" }}
                        tickLine={false}
                        axisLine={false}
                        interval={0}
                        height={56}
                      />
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
                        formatter={(value: number, name: string, item: { payload?: Record<string, unknown> }) => {
                          const p = item.payload ?? {};
                          if (name === "Current" && p.currentMissing) return ["—", "Current"];
                          if (name === "Baseline" && p.baselineMissing) return ["—", "Baseline"];
                          return [value.toLocaleString(undefined, { maximumFractionDigits: 2 }), name];
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: "12px", color: "#0f172a" }} />
                      <Bar dataKey="current" name="Current" fill="#0d9488" radius={[4, 4, 0, 0]} maxBarSize={32} />
                      <Bar dataKey="baseline" name="Baseline" fill="#94a3b8" radius={[4, 4, 0, 0]} maxBarSize={32} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-1 text-[11px] text-ink-muted">
                  Chart maps missing periods to zero for layout; the table shows &quot;—&quot; where data is absent.
                </p>
              </div>
            ) : null}
            <div className="overflow-x-auto rounded-xl border border-border/60 bg-surface-subtle/50">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    <th className="py-3 pl-4 pr-4">Name</th>
                    <th className="py-3 pr-4 text-right">Current</th>
                    <th className="py-3 pr-4 text-right">Baseline</th>
                    <th className="py-3 pr-4 text-right">Δ</th>
                    <th className="py-3 pr-4 text-right">%</th>
                  </tr>
                </thead>
                <tbody>
                  {compare.data.rows.map((row, i) => (
                    <tr key={i} className="border-b border-slate-100/80 transition-colors hover:bg-white/80">
                      <td className="py-2.5 pl-4 pr-4 text-ink">
                        {(row.division_name as string) ||
                          (row.business_unit_name as string) ||
                          (row.org_name as string)}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-sm">
                        {row.current_missing ? "—" : (row.current_revenue as string)}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-sm">
                        {row.comparison_missing ? "—" : (row.comparison_revenue as string)}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-sm">{row.absolute_change as string}</td>
                      <td className="py-2.5 pr-4 text-right font-mono text-sm text-ink">
                        {row.percent_change == null ? "—" : (row.percent_change as string)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {compare.data.rows.length === 0 ? (
              <p className="text-sm text-ink-muted">No rows in either period for these filters.</p>
            ) : null}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">
            {compare.isLoading ? "Loading…" : orgId ? "" : "Select an organization."}
          </p>
        )}
      </section>

      <section className="surface-card border-dashed border-primary/20 bg-gradient-to-br from-slate-50/80 to-cyan-50/30 p-6 text-sm text-ink">
        <h2 className="font-semibold text-ink">Freshness</h2>
        {freshness.isLoading ? (
          <p className="mt-2 text-ink-muted">Loading…</p>
        ) : freshness.data ? (
          <div className="mt-3 space-y-2">
            {freshness.data.structures.length === 0 ? (
              <p className="text-ink-muted">No materialized refresh recorded yet (run an import to populate).</p>
            ) : (
              <ul className="space-y-2">
                {freshness.data.structures.map((s) => (
                  <li
                    key={s.structure_name}
                    className="flex flex-wrap items-baseline gap-2 rounded-lg border border-border/60 bg-white/60 px-3 py-2 text-xs"
                  >
                    <span className="font-mono text-[11px] text-primary">{s.structure_name}</span>
                    {s.last_refresh_completed_at ? (
                      <span className="text-ink-muted">— {s.last_refresh_completed_at}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-ink-muted">{freshness.data.notes}</p>
          </div>
        ) : (
          <p className="mt-2 text-red-700">Could not load freshness.</p>
        )}
      </section>
    </div>
  );
}
