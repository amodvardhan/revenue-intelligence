import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/services/api";

const phase5 = import.meta.env.VITE_ENABLE_PHASE5 === "true";

export function ForecastingPage() {
  const [seriesId, setSeriesId] = useState("");

  const series = useQuery({
    queryKey: ["forecast-series"],
    queryFn: async () => {
      const { data } = await api.get<{ items: Array<{ forecast_series_id: string; label: string; source_mode: string }> }>(
        "/api/v1/forecast/series",
      );
      return data;
    },
    enabled: phase5,
  });

  if (!phase5) {
    return (
      <div className="page-shell page-shell--md page-shell--tight">
        <h1 className="page-headline">Forecasting</h1>
        <p className="mt-2 text-sm text-ink-muted">Set VITE_ENABLE_PHASE5=true and ENABLE_PHASE5=true on the API to use this screen.</p>
      </div>
    );
  }

  return (
    <div className="page-shell page-shell--md">
      <header className="page-header-block">
        <h1 className="page-headline">Forecasting</h1>
        <p className="page-lede max-w-2xl">
          Forecast views are informational and are not audited financial statements unless Finance exports and signs off
          outside the product.
        </p>
      </header>

      <div className="rounded-xl border border-amber-200/90 bg-amber-50/90 px-4 py-3 text-sm text-amber-950">
        <strong className="font-semibold">Disclaimer:</strong> Forward-looking amounts are not audited actuals. Do not
        treat forecast as booked revenue.
      </div>

      <section className="surface-card p-6">
        <h2 className="text-heading">Forecast series</h2>
        {series.isLoading ? <p className="mt-2 text-sm text-ink-muted">Loading…</p> : null}
        {series.isError ? (
          <p className="mt-2 text-sm text-error">Could not load series (is ENABLE_PHASE5 enabled on the API?).</p>
        ) : null}
        <ul className="mt-3 space-y-1">
          {(series.data?.items ?? []).map((s) => (
            <li key={s.forecast_series_id} className="text-sm text-ink">
              <button
                type="button"
                className="text-left font-medium text-primary underline-offset-2 hover:underline"
                onClick={() => setSeriesId(s.forecast_series_id)}
              >
                {s.label}
              </button>{" "}
              <span className="text-xs text-ink-muted">({s.source_mode})</span>
            </li>
          ))}
        </ul>
      </section>
      {seriesId ? (
        <p className="text-xs text-ink-muted">
          Selected series: <span className="font-mono">{seriesId}</span> — use GET /forecast/facts for detail.
        </p>
      ) : null}
    </div>
  );
}
