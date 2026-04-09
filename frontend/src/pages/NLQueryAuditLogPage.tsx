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
      <div className="page-shell page-shell--narrow page-shell--tight">
        <p className="text-sm text-ink-muted">Loading audit log…</p>
      </div>
    );
  }

  if (q.isError) {
    return (
      <div className="page-shell page-shell--narrow">
        <h1 className="page-headline">Query audit log</h1>
        <NLQuerySafetyMessage
          title="Access denied or unavailable"
          message={apiErrorMessage(q.error)}
          variant="warning"
        />
        <p className="mt-4 text-sm text-ink-muted">
          <Link to="/ask" className="font-medium text-primary underline-offset-2 hover:underline">
            Back to Ask revenue
          </Link>
        </p>
      </div>
    );
  }

  const data = q.data;

  return (
    <div className="page-shell page-shell--narrow">
      <header className="page-header-block">
        <h1 className="page-headline">Query audit log</h1>
        <p className="page-lede max-w-2xl">
          Operational retention defaults to 365 days. Who asked what, when, and outcome — for IT and Finance governance.
        </p>
      </header>

      <div className="table-modern-wrap mt-2">
        <table className="table-modern">
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>Question</th>
              <th>Status</th>
              <th className="text-right">Rows</th>
              <th className="text-right">ms</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-10 text-center text-sm text-ink-muted">
                  No audit entries in this range.
                </td>
              </tr>
            ) : (
              data?.items.map((row) => (
                <tr key={row.log_id}>
                  <td className="whitespace-nowrap font-mono text-[13px]">{row.created_at}</td>
                  <td className="max-w-[120px] truncate font-mono text-xs text-ink-muted">{row.user_id ?? "—"}</td>
                  <td className="max-w-md truncate">{row.natural_query}</td>
                  <td>{row.status ?? "—"}</td>
                  <td className="text-right font-mono tabular-nums text-[13px]">{row.row_count ?? "—"}</td>
                  <td className="text-right font-mono tabular-nums text-[13px]">{row.execution_ms ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
