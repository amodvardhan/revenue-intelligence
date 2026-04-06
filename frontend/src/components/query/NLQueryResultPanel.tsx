interface NLQueryResultPanelProps {
  columns: string[];
  rows: Record<string, string | null | undefined>[];
}

export function NLQueryResultPanel({ columns, rows }: NLQueryResultPanelProps) {
  if (rows.length === 0) {
    return (
      <div className="mt-4 rounded-md border border-dashed border-border bg-white p-6 text-center text-sm text-slate-600">
        No rows returned for this question.
      </div>
    );
  }

  return (
    <div className="mt-4 overflow-x-auto rounded-md border border-border bg-white shadow-sm">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-slate-50 text-left">
            {columns.map((c) => (
              <th key={c} className="px-3 py-2 font-medium text-slate-700">
                {c.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/80">
              {columns.map((c) => (
                <td
                  key={c}
                  className="px-3 py-2 tabular-nums text-slate-900"
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
