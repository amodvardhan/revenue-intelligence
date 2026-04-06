import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { Link } from "react-router-dom";

import { NLQuerySafetyMessage } from "@/components/query/NLQuerySafetyMessage";
import { api } from "@/services/api";
import type { AuditListResponse } from "@/types/query";

function apiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err) && err.response?.data && typeof err.response.data === "object") {
    const d = err.response.data as { error?: { message?: string } };
    if (d.error?.message) return d.error.message;
  }
  return err instanceof Error ? err.message : "Request failed";
}

export function NLQueryAuditLogPage() {
  const q = useQuery({
    queryKey: ["query-audit"],
    queryFn: async () => {
      const { data } = await api.get<AuditListResponse>("/api/v1/query/audit", {
        params: { limit: 50 },
      });
      return data;
    },
    retry: false,
  });

  if (q.isLoading) {
    return (
      <div className="p-6">
        <p className="text-sm text-slate-600">Loading audit log…</p>
      </div>
    );
  }

  if (q.isError) {
    return (
      <div className="p-6 max-w-3xl">
        <h1 className="text-display text-2xl font-semibold text-slate-900">Query audit log</h1>
        <NLQuerySafetyMessage
          title="Access denied or unavailable"
          message={apiErrorMessage(q.error)}
          variant="warning"
        />
        <p className="mt-4 text-sm text-slate-600">
          <Link to="/ask" className="text-primary underline">
            Back to Ask revenue
          </Link>
        </p>
      </div>
    );
  }

  const data = q.data;

  return (
    <div className="p-6">
      <h1 className="text-display text-2xl font-semibold text-slate-900">Query audit log</h1>
      <p className="mt-1 text-small text-slate-600">
        Operational retention defaults to 365 days. Who asked what, when, and outcome — for IT and Finance
        governance.
      </p>

      <div className="mt-6 overflow-x-auto rounded-md border border-border bg-white shadow-sm">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-slate-50 text-left">
              <th className="px-3 py-2 font-medium text-slate-700">When</th>
              <th className="px-3 py-2 font-medium text-slate-700">Who</th>
              <th className="px-3 py-2 font-medium text-slate-700">Question</th>
              <th className="px-3 py-2 font-medium text-slate-700">Status</th>
              <th className="px-3 py-2 font-medium text-slate-700">Rows</th>
              <th className="px-3 py-2 font-medium text-slate-700">ms</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-slate-600">
                  No audit entries in this range.
                </td>
              </tr>
            ) : (
              data?.items.map((row) => (
                <tr key={row.log_id} className="border-b border-slate-100 hover:bg-slate-50/80">
                  <td className="whitespace-nowrap px-3 py-2 text-slate-800">{row.created_at}</td>
                  <td className="max-w-[120px] truncate px-3 py-2 font-mono text-xs text-slate-700">
                    {row.user_id ?? "—"}
                  </td>
                  <td className="max-w-md truncate px-3 py-2 text-slate-800">{row.natural_query}</td>
                  <td className="px-3 py-2">{row.status ?? "—"}</td>
                  <td className="px-3 py-2 tabular-nums">{row.row_count ?? "—"}</td>
                  <td className="px-3 py-2 tabular-nums">{row.execution_ms ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
