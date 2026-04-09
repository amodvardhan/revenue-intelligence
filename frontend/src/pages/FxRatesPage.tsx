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
      <div className="page-shell page-shell--md page-shell--tight">
        <h1 className="page-headline">FX rates</h1>
        <p className="mt-2 text-sm text-ink-muted">Set VITE_ENABLE_PHASE5=true and ENABLE_PHASE5=true on the API to use this screen.</p>
      </div>
    );
  }

  return (
    <div className="page-shell page-shell--md">
      <header className="page-header-block">
        <h1 className="page-headline">FX rates</h1>
        <p className="page-lede max-w-2xl">
          Manual upload v1 — POST /fx-rates/uploads with CSV (base, quote, effective_date, rate).
        </p>
      </header>

      {settings.data ? (
        <p className="text-sm text-ink">
          Reporting currency: <strong className="font-semibold">{settings.data.reporting_currency_code}</strong>
        </p>
      ) : null}

      {rates.isLoading ? <p className="text-sm text-ink-muted">Loading rates…</p> : null}
      {rates.isError ? <p className="text-sm text-error">Could not load rates.</p> : null}

      <div className="table-modern-wrap">
        <table className="table-modern">
          <thead>
            <tr>
              <th>Pair</th>
              <th>Effective</th>
              <th className="text-right">Rate</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {(rates.data?.items ?? []).map((r, i) => (
              <tr key={i}>
                <td className="font-mono text-[13px]">
                  {r.base_currency_code}/{r.quote_currency_code}
                </td>
                <td className="font-mono text-[13px]">{r.effective_date}</td>
                <td className="text-right font-mono tabular-nums text-[13px]">{r.rate}</td>
                <td className="text-ink-muted">{r.rate_source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
