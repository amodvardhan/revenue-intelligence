interface NLQueryResultPanelProps {
  columns: string[];
  rows: Record<string, string | null | undefined>[];
}

export function NLQueryResultPanel({ columns, rows }: NLQueryResultPanelProps) {
  if (rows.length === 0) {
    return (
      <div className="mt-4 rounded-2xl border border-dashed border-border bg-surface-subtle/50 px-6 py-10 text-center text-sm text-ink-muted">
        No rows returned for this question.
      </div>
    );
  }

  return (
    <div className="mt-4 overflow-x-auto rounded-2xl border border-border/80 bg-white shadow-card">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-gradient-to-r from-slate-50 to-teal-50/30 text-left">
            {columns.map((c) => (
              <th key={c} className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                {c.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-slate-100/90 transition-colors hover:bg-teal-50/30">
              {columns.map((c) => (
                <td
                  key={c}
                  className={`px-4 py-2.5 text-sm text-ink ${/revenue|change|percent|amount/i.test(c) ? "font-mono tabular-nums" : ""}`}
                  style={
                    /revenue|change|percent/i.test(c)
                      ? { textAlign: "right" as const }
                      : undefined
                  }
                >
                  {row[c] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
