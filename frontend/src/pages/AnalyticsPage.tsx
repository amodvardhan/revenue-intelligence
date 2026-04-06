import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/services/api";

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

  return (
    <div className="max-w-6xl space-y-8 p-6">
      <header>
        <h1 className="text-display text-3xl font-semibold text-slate-900">Analytics</h1>
        <p className="mt-1 text-sm text-slate-600">
          Hierarchical rollups and period-over-period comparisons. Totals use the same underlying facts as the{" "}
          <Link to="/revenue" className="font-medium text-primary underline-offset-2 hover:underline">
            Revenue
          </Link>{" "}
          view when you use the same organization and filters.
        </p>
      </header>

      <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
        <strong className="font-medium text-slate-800">Explicit periods only.</strong> All ranges use the date fields
        below—there are no presets such as &quot;last quarter&quot; without showing the exact from/to dates (Story 2.2).
      </p>

      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-[220px]">
          <label htmlFor="analytics-org" className="mb-1 block text-sm font-medium text-slate-700">
            Organization
          </label>
          <select
            id="analytics-org"
            className="h-10 w-full rounded-md border border-border px-3 text-sm focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary"
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
          <label htmlFor="analytics-hierarchy" className="mb-1 block text-sm font-medium text-slate-700">
            Hierarchy
          </label>
          <select
            id="analytics-hierarchy"
            className="h-10 rounded-md border border-border px-3 text-sm focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary"
            value={hierarchy}
            onChange={(e) => setHierarchy(e.target.value as Hierarchy)}
          >
            <option value="org">Organization</option>
            <option value="bu">Business unit</option>
            <option value="division">Division</option>
          </select>
        </div>
        <div>
          <label htmlFor="analytics-from" className="mb-1 block text-sm font-medium text-slate-700">
            Rollup from
          </label>
          <input
            id="analytics-from"
            type="date"
            className="h-10 rounded-md border border-border px-3 text-sm focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="analytics-to" className="mb-1 block text-sm font-medium text-slate-700">
            Rollup to
          </label>
          <input
            id="analytics-to"
            type="date"
            className="h-10 rounded-md border border-border px-3 text-sm focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
      </div>

      <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Rollup</h2>
        <p className="mt-1 text-xs text-slate-500">
          Drill-down: open{" "}
          <Link to="/revenue" className="text-primary underline-offset-2 hover:underline">
            Revenue
          </Link>{" "}
          and apply the same organization and date range to reconcile row-level facts.
        </p>
        {rollup.isError ? (
          <p className="mt-2 text-sm text-red-700">Could not load rollup.</p>
        ) : null}
        {rollup.data ? (
          <div className="mt-3 space-y-2">
            <p className="text-xs text-slate-500">
              As of {rollup.data.as_of} · grain {rollup.data.hierarchy}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-slate-600">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4 text-right">Revenue</th>
                    <th className="py-2 text-right">Child count</th>
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
                      <tr key={i} className="border-b border-slate-100">
                        <td className="py-2 pr-4">
                          {(row.division_name as string) ||
                            (row.business_unit_name as string) ||
                            (row.org_name as string)}
                        </td>
                        <td className="py-2 pr-4 text-right font-mono tabular-nums">
                          {row.revenue as string}
                        </td>
                        <td className="py-2 text-right text-slate-600">{String(row.child_count ?? "")}</td>
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

      <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Compare</h2>
        <p className="mt-1 text-xs text-slate-500">
          MoM / QoQ / YoY labels describe the comparison style; the numbers always use the <strong>exact</strong> current
          and baseline date ranges you set (not ambiguous rolling windows).
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="analytics-compare-kind" className="mb-1 block text-xs font-medium text-slate-600">
              Compare style
            </label>
            <select
              id="analytics-compare-kind"
              className="h-9 rounded-md border border-border px-2 text-sm focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary"
              value={compareKind}
              onChange={(e) => setCompareKind(e.target.value as CompareKind)}
            >
              <option value="mom">MoM</option>
              <option value="qoq">QoQ</option>
              <option value="yoy">YoY</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-600">Current from / to</label>
            <div className="flex gap-1">
              <input
                type="date"
                className="h-9 rounded-md border border-border px-2 text-sm"
                value={curFrom}
                onChange={(e) => setCurFrom(e.target.value)}
              />
              <input
                type="date"
                className="h-9 rounded-md border border-border px-2 text-sm"
                value={curTo}
                onChange={(e) => setCurTo(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-600">Baseline from / to</label>
            <div className="flex gap-1">
              <input
                type="date"
                className="h-9 rounded-md border border-border px-2 text-sm"
                value={cmpFrom}
                onChange={(e) => setCmpFrom(e.target.value)}
              />
              <input
                type="date"
                className="h-9 rounded-md border border-border px-2 text-sm"
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
          <div className="mt-4 space-y-2">
            <p className="text-xs text-slate-500">
              Current: {compare.data.current_period.label} · Baseline: {compare.data.comparison_period.label} · As of{" "}
              {compare.data.as_of}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-slate-600">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4 text-right">Current</th>
                    <th className="py-2 pr-4 text-right">Baseline</th>
                    <th className="py-2 pr-4 text-right">Δ</th>
                    <th className="py-2 text-right">%</th>
                  </tr>
                </thead>
                <tbody>
                  {compare.data.rows.map((row, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="py-2 pr-4">
                        {(row.division_name as string) ||
                          (row.business_unit_name as string) ||
                          (row.org_name as string)}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono">
                        {row.current_missing ? "—" : (row.current_revenue as string)}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono">
                        {row.comparison_missing ? "—" : (row.comparison_revenue as string)}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono">{row.absolute_change as string}</td>
                      <td className="py-2 text-right font-mono text-slate-700">
                        {row.percent_change == null ? "—" : (row.percent_change as string)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {compare.data.rows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">No rows in either period for these filters.</p>
            ) : null}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">
            {compare.isLoading ? "Loading…" : orgId ? "" : "Select an organization."}
          </p>
        )}
      </section>

      <section className="rounded-lg border border-border bg-slate-50 p-4 text-sm text-slate-700">
        <h2 className="font-semibold text-slate-900">Freshness</h2>
        {freshness.isLoading ? (
          <p className="mt-2">Loading…</p>
        ) : freshness.data ? (
          <div className="mt-2 space-y-1">
            {freshness.data.structures.length === 0 ? (
              <p className="text-slate-600">No materialized refresh recorded yet (run an import to populate).</p>
            ) : (
              <ul className="list-inside list-disc space-y-1">
                {freshness.data.structures.map((s) => (
                  <li key={s.structure_name}>
                    <span className="font-mono text-xs">{s.structure_name}</span>
                    {s.last_refresh_completed_at ? (
                      <span className="text-slate-600"> — {s.last_refresh_completed_at}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-slate-500">{freshness.data.notes}</p>
          </div>
        ) : (
          <p className="mt-2 text-red-700">Could not load freshness.</p>
        )}
      </section>
    </div>
  );
}
