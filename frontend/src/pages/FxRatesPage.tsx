import { useQuery } from "@tanstack/react-query";

import { api } from "@/services/api";

const phase5 = import.meta.env.VITE_ENABLE_PHASE5 === "true";

export function FxRatesPage() {
  const settings = useQuery({
    queryKey: ["tenant-settings"],
    queryFn: async () => {
      const { data } = await api.get<{ reporting_currency_code: string }>("/api/v1/tenant/settings");
      return data;
    },
    enabled: phase5,
  });

  const rates = useQuery({
    queryKey: ["fx-rates"],
    queryFn: async () => {
      const { data } = await api.get<{
        items: Array<{
          base_currency_code: string;
          quote_currency_code: string;
          effective_date: string;
          rate: string;
          rate_source: string;
        }>;
      }>("/api/v1/fx-rates");
      return data;
    },
    enabled: phase5,
  });

  if (!phase5) {
    return (
      <div className="p-8">
        <h1 className="text-display text-slate-900">FX rates</h1>
        <p className="mt-2 text-sm text-slate-600">Set VITE_ENABLE_PHASE5=true and ENABLE_PHASE5=true on the API.</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-display text-slate-900">FX rates</h1>
      {settings.data ? (
        <p className="mt-2 text-sm text-slate-700">
          Reporting currency: <strong>{settings.data.reporting_currency_code}</strong>
        </p>
      ) : null}
      <p className="mt-2 text-sm text-slate-600">Manual upload v1 — POST /fx-rates/uploads with CSV (base, quote, effective_date, rate).</p>
      {rates.isLoading ? <p className="mt-4 text-sm">Loading rates…</p> : null}
      {rates.isError ? <p className="mt-4 text-sm text-red-600">Could not load rates.</p> : null}
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b text-left text-slate-600">
              <th className="py-2 pr-4">Pair</th>
              <th className="py-2 pr-4">Effective</th>
              <th className="py-2 pr-4">Rate</th>
              <th className="py-2">Source</th>
            </tr>
          </thead>
          <tbody>
            {(rates.data?.items ?? []).map((r, i) => (
              <tr key={i} className="border-b border-slate-100">
                <td className="py-2 pr-4 font-mono">
                  {r.base_currency_code}/{r.quote_currency_code}
                </td>
                <td className="py-2 pr-4">{r.effective_date}</td>
                <td className="py-2 pr-4 font-mono tabular-nums">{r.rate}</td>
                <td className="py-2 text-slate-600">{r.rate_source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
