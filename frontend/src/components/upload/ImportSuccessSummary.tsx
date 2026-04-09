import { CheckCircle2, Copy } from "lucide-react";

interface ImportSuccessSummaryProps {
  batchId: string;
  filename: string;
  loadedRows: number;
  totalRows: number | null;
  periodStart?: string | null;
  periodEnd?: string | null;
  completedAt?: string | null;
}

export function ImportSuccessSummary({
  batchId,
  filename,
  loadedRows,
  totalRows,
  periodStart,
  periodEnd,
  completedAt,
}: ImportSuccessSummaryProps) {
  const copy = async () => {
    await navigator.clipboard.writeText(batchId);
  };

  return (
    <div className="rounded-lg border border-success bg-success-surface p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <CheckCircle2 className="h-8 w-8 shrink-0 text-success" aria-hidden />
        <div className="flex-1 space-y-3">
          <h3 className="text-heading text-[18px]">Import complete</h3>
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-ink-muted">Batch ID</dt>
              <dd className="flex items-center gap-2 font-mono text-xs">
                <span className="truncate">{batchId}</span>
                <button
                  type="button"
                  className="shrink-0 rounded p-1 text-primary hover:bg-primary-muted"
                  aria-label="Copy batch id"
                  onClick={copy}
                >
                  <Copy className="h-4 w-4" />
                </button>
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">File</dt>
              <dd className="break-all">{filename}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Rows loaded</dt>
              <dd>
                {loadedRows}
                {totalRows !== null ? ` / ${totalRows}` : ""}
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">Period</dt>
              <dd>
                {periodStart ?? "—"} → {periodEnd ?? "—"}
              </dd>
            </div>
            {completedAt ? (
              <div className="sm:col-span-2">
                <dt className="text-ink-muted">Completed at</dt>
                <dd>{new Date(completedAt).toLocaleString()}</dd>
              </div>
            ) : null}
          </dl>
          <p className="text-sm text-ink-muted">Next: Review revenue for this period.</p>
        </div>
      </div>
    </div>
  );
}
