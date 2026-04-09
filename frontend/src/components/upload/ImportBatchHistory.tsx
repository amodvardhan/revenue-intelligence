import { CheckCircle2, History, Loader2, XCircle } from "lucide-react";

export interface BatchRow {
  batch_id: string;
  filename: string | null;
  status: string;
  total_rows: number | null;
  loaded_rows: number;
  started_at: string;
  completed_at: string | null;
}

interface ImportBatchHistoryProps {
  items: BatchRow[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />;
  if (status === "failed" || status === "rejected") return <XCircle className="h-4 w-4 text-error" aria-hidden />;
  return <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />;
}

export function ImportBatchHistory({ items, loading, error, onRetry }: ImportBatchHistoryProps) {
  return (
    <section className="mt-8 space-y-3">
      <div className="flex items-center gap-2 text-heading">
        <History className="h-5 w-5" aria-hidden />
        Recent imports
      </div>
      {error ? (
        <div className="rounded border border-error bg-error-surface p-3 text-sm text-error">
          {error}
          {onRetry ? (
            <button type="button" className="ml-2 underline" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
      {loading ? (
        <div className="h-24 animate-pulse rounded border border-border bg-white" />
      ) : items.length === 0 ? (
        <p className="text-sm text-ink-muted">No imports yet — upload a file above.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-surface-subtle text-left text-body-strong">
              <tr>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">File</th>
                <th className="px-3 py-2">Completed</th>
                <th className="px-3 py-2">Rows</th>
                <th className="px-3 py-2">Batch ID</th>
              </tr>
            </thead>
            <tbody>
              {items.map((b) => (
                <tr key={b.batch_id} className="border-t border-border">
                  <td className="px-3 py-2">
                    <span className="inline-flex items-center gap-1 capitalize">
                      <StatusIcon status={b.status} />
                      {b.status}
                    </span>
                  </td>
                  <td className="px-3 py-2">{b.filename ?? "—"}</td>
                  <td className="px-3 py-2 text-ink-muted">
                    {b.completed_at ? new Date(b.completed_at).toLocaleString() : "—"}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {b.loaded_rows}/{b.total_rows ?? "—"}
                  </td>
                  <td className="max-w-[12rem] truncate px-3 py-2 font-mono text-xs" title={b.batch_id}>
                    {b.batch_id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
