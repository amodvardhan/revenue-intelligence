interface FilePreviewTableProps {
  headers: string[];
  rows: (string | number | null | undefined)[][];
  fileName: string;
  approxRows?: number;
  loading?: boolean;
  error?: string | null;
}

export function FilePreviewTable({
  headers,
  rows,
  fileName,
  approxRows,
  loading,
  error,
}: FilePreviewTableProps) {
  if (error) {
    return (
      <div className="rounded-md border border-error bg-error-surface p-4 text-sm text-error">
        Could not read this file. {error}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-md border border-border bg-surface-elevated p-4">
        <div className="h-4 w-1/3 animate-pulse rounded bg-neutral-200" />
        <div className="mt-4 space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-8 animate-pulse rounded bg-neutral-100" />
          ))}
        </div>
      </div>
    );
  }

  if (headers.length === 0 && rows.length === 0) {
    return null;
  }

  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface-elevated shadow-sm">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-heading">Preview (first 5 rows)</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="bg-surface-subtle text-left text-body-strong">
              {headers.map((h, i) => (
                <th key={`col-${i}-${String(h)}`} className="border-b border-border px-3 py-2 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-surface-subtle"}>
                {r.map((c, j) => (
                  <td
                    key={j}
                    className={`border-b border-border px-3 py-2 ${String(headers[j] ?? "").includes("amount") ? "font-mono text-right tabular-nums" : ""}`}
                  >
                    {c === null || c === undefined ? "" : String(c)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-border px-4 py-2 text-xs text-ink-muted">
        {fileName}
        {approxRows !== undefined ? ` · ~${approxRows} rows` : null}
      </div>
    </div>
  );
}
