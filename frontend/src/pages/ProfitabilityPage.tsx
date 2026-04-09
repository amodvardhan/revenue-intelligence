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
      <div className="page-shell page-shell--md page-shell--tight">
        <h1 className="page-headline">Profitability</h1>
        <p className="mt-2 text-sm text-ink-muted">Set VITE_ENABLE_PHASE5=true and ENABLE_PHASE5=true on the API to use this screen.</p>
      </div>
    );
  }

  return (
    <div className="page-shell page-shell--md">
      <header className="page-header-block">
        <h1 className="page-headline">Profitability</h1>
        <p className="page-lede max-w-2xl">COGS-only scope when cost_scope=cogs_only; upload costs via POST /ingest/cost-uploads.</p>
      </header>

      <div className="surface-card-quiet flex flex-wrap gap-4 p-4">
        <label className="flex items-center gap-2 text-sm text-ink">
          From
          <input
            className="input-modern !h-10 w-[11rem] font-mono text-[13px]"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-ink">
          To
          <input className="input-modern !h-10 w-[11rem] font-mono text-[13px]" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
      </div>

      {summary.isLoading ? <p className="text-sm text-ink-muted">Loading…</p> : null}
      {summary.isError ? <p className="text-sm text-error">Unable to load summary (enable Phase 5 on the API).</p> : null}
      {summary.data ? (
        <div className="surface-card max-w-md p-6">
          <dl className="grid gap-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-muted">Revenue</dt>
              <dd className="font-mono tabular-nums text-ink">
                {summary.data.revenue_total} {summary.data.currency_code}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-muted">Cost</dt>
              <dd className="font-mono tabular-nums text-ink">
                {summary.data.cost_total} {summary.data.currency_code}
              </dd>
            </div>
            <div className="flex justify-between gap-4 font-semibold">
              <dt className="text-ink">Margin</dt>
              <dd className="font-mono tabular-nums text-ink">
                {summary.data.margin} {summary.data.currency_code}
              </dd>
            </div>
            <p className="pt-2 text-xs text-ink-muted">{summary.data.methodology_note}</p>
          </dl>
        </div>
      ) : null}
    </div>
  );
}
