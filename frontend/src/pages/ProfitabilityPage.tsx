import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/services/api";

const phase5 = import.meta.env.VITE_ENABLE_PHASE5 === "true";

export function ProfitabilityPage() {
  const [from, setFrom] = useState("2026-01-01");
  const [to, setTo] = useState("2026-03-31");

  const summary = useQuery({
    queryKey: ["profitability-summary", from, to],
    queryFn: async () => {
      const { data } = await api.get("/api/v1/analytics/profitability/summary", {
        params: { period_start: from, period_end: to, cost_scope: "cogs_only" },
      });
      return data as {
        revenue_total: string;
        cost_total: string;
        margin: string;
        currency_code: string;
        methodology_note: string;
      };
    },
    enabled: phase5,
  });

  if (!phase5) {
    return (
      <div className="p-8">
        <h1 className="text-display text-slate-900">Profitability</h1>
        <p className="mt-2 text-sm text-slate-600">Set VITE_ENABLE_PHASE5=true and ENABLE_PHASE5=true on the API.</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-display text-slate-900">Profitability</h1>
      <div className="mt-2 rounded-md bg-slate-100 p-3 text-sm text-slate-700">
        Scope: COGS-only costs are shown when cost_scope=cogs_only; upload costs via POST /ingest/cost-uploads.
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <label className="text-sm">
          From{" "}
          <input className="ml-1 rounded border px-2 py-1" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className="text-sm">
          To{" "}
          <input className="ml-1 rounded border px-2 py-1" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
      </div>
      {summary.isLoading ? <p className="mt-4 text-sm">Loading…</p> : null}
      {summary.isError ? (
        <p className="mt-4 text-sm text-red-600">Unable to load summary (enable Phase 5 on the API).</p>
      ) : null}
      {summary.data ? (
        <dl className="mt-6 grid max-w-md gap-2 text-sm">
          <div className="flex justify-between">
            <dt>Revenue</dt>
            <dd className="font-mono tabular-nums">
              {summary.data.revenue_total} {summary.data.currency_code}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt>Cost</dt>
            <dd className="font-mono tabular-nums">
              {summary.data.cost_total} {summary.data.currency_code}
            </dd>
          </div>
          <div className="flex justify-between font-semibold">
            <dt>Margin</dt>
            <dd className="font-mono tabular-nums">
              {summary.data.margin} {summary.data.currency_code}
            </dd>
          </div>
          <p className="col-span-2 mt-2 text-xs text-slate-500">{summary.data.methodology_note}</p>
        </dl>
      ) : null}
    </div>
  );
}
