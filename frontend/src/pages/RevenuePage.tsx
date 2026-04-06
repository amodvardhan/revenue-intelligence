import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "@/services/api";

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

  return (
    <div className="max-w-6xl space-y-6 p-6">
      <header>
        <h1 className="text-display text-3xl font-semibold text-slate-900">Revenue</h1>
        <p className="mt-1 text-sm text-slate-600">
          Imported facts from <code className="font-mono text-xs">fact_revenue</code> for your organization scope.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-[220px]">
          <label className="mb-1 block text-sm font-medium text-slate-700">Organization</label>
          <select
            className="h-10 w-full rounded-md border border-border px-3 text-sm"
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
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          Could not load revenue.{" "}
          {revenue.error instanceof Error ? revenue.error.message : "Check the API and your session."}
        </div>
      ) : null}

      {!orgId && !orgs.isLoading ? (
        <div className="rounded-lg border border-dashed border-border bg-white px-6 py-12 text-center text-sm text-slate-600">
          Select an organization to load revenue rows. If the list is empty, register or ask an admin to assign org
          access.
        </div>
      ) : null}

      {orgId && revenue.isSuccess && revenue.data.items.length === 0 ? (
        <div className="rounded-lg border border-border bg-white px-6 py-12 text-center text-sm text-slate-600">
          No revenue rows for this organization yet. Import an Excel file on the Import page, then return here.
        </div>
      ) : null}

      {orgId && revenue.isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : null}

      {orgId && revenue.isSuccess && revenue.data.items.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border bg-white shadow-sm">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-600">
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
                <tr key={row.revenue_id} className="hover:bg-slate-50/80">
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-slate-900">{row.revenue_date}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-slate-900">{row.amount}</td>
                  <td className="px-4 py-3 text-slate-600">{row.currency_code}</td>
                  <td className="px-4 py-3 text-slate-700">{row.source_system}</td>
                  <td className="hidden px-4 py-3 font-mono text-xs text-slate-500 md:table-cell">
                    {row.batch_id ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {revenue.data.next_cursor ? (
            <p className="border-t border-border px-4 py-2 text-xs text-slate-500">
              More rows available — pagination via API cursor not yet wired in this view.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
