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
        "/api/v1/forecast/series"
      );
      return data;
    },
    enabled: phase5,
  });

  if (!phase5) {
    return (
      <div className="p-8">
        <h1 className="text-display text-slate-900">Forecasting</h1>
        <p className="mt-2 text-sm text-slate-600">Set VITE_ENABLE_PHASE5=true and ENABLE_PHASE5=true on the API to use this screen.</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-display text-slate-900">Forecasting</h1>
      <p className="mt-1 text-sm text-slate-600">
        Forecast views are informational and are not audited financial statements unless Finance exports and signs off outside the product.
      </p>
      <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        <strong>Disclaimer:</strong> Forward-looking amounts are not audited actuals. Do not treat forecast as booked revenue.
      </div>
      <section className="mt-8">
        <h2 className="text-heading font-semibold text-slate-800">Forecast series</h2>
        {series.isLoading ? <p className="mt-2 text-sm text-slate-500">Loading…</p> : null}
        {series.isError ? (
          <p className="mt-2 text-sm text-red-600">Could not load series (is ENABLE_PHASE5 enabled on the API?).</p>
        ) : null}
        <ul className="mt-2 space-y-1">
          {(series.data?.items ?? []).map((s) => (
            <li key={s.forecast_series_id} className="text-sm text-slate-700">
              <button
                type="button"
                className="text-left text-primary underline"
                onClick={() => setSeriesId(s.forecast_series_id)}
              >
                {s.label}
              </button>{" "}
              <span className="text-xs text-slate-500">({s.source_mode})</span>
            </li>
          ))}
        </ul>
      </section>
      {seriesId ? (
        <p className="mt-4 text-xs text-slate-500">Selected series: {seriesId} — use GET /forecast/facts for detail.</p>
      ) : null}
    </div>
  );
}
