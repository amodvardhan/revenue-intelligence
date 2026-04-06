import { AlertTriangle } from "lucide-react";

interface Err {
  row?: number | null;
  column?: string | null;
  message: string;
}

interface ImportErrorListProps {
  errors: Err[];
}

export function ImportErrorList({ errors }: ImportErrorListProps) {
  if (errors.length === 0) {
    return (
      <div className="rounded border border-error bg-error-surface p-4 text-sm text-error">
        Validation failed. Contact support with batch id.
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded border border-error bg-error-surface p-4">
      <div className="flex items-start gap-2 font-medium text-error">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
        <span>Import failed — no data was loaded.</span>
      </div>
      <div className="max-h-80 overflow-y-auto rounded border border-border bg-white">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 bg-surface-subtle">
            <tr>
              <th className="px-3 py-2 text-left">Row</th>
              <th className="px-3 py-2 text-left">Column</th>
              <th className="px-3 py-2 text-left">Message</th>
            </tr>
          </thead>
          <tbody>
            {errors.map((e, i) => (
              <tr key={i} className="border-t border-border">
                <td className="px-3 py-2 font-mono">{e.row ?? "—"}</td>
                <td className="px-3 py-2 font-mono">{e.column ?? "—"}</td>
                <td className="px-3 py-2">{e.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
