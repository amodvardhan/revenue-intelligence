import { CheckCircle2, Copy, Loader2 } from "lucide-react";

interface IngestionProgressTrackerProps {
  step: "upload" | "validate" | "commit";
  asyncMode?: boolean;
  batchId?: string;
}

export function IngestionProgressTracker({ step, asyncMode, batchId }: IngestionProgressTrackerProps) {
  const steps: Array<{ id: typeof step; label: string }> = [
    { id: "upload", label: "Upload" },
    { id: "validate", label: "Validate" },
    { id: "commit", label: "Commit" },
  ];
  const idx = steps.findIndex((s) => s.id === step);

  const copy = async () => {
    if (batchId) await navigator.clipboard.writeText(batchId);
  };

  return (
    <div className="rounded-md border border-border bg-white p-4">
      <ol className="flex flex-wrap items-center gap-4">
        {steps.map((s, i) => (
          <li key={s.id} className="flex items-center gap-2 text-sm">
            {i < idx ? (
              <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />
            ) : i === idx ? (
              <Loader2 className="h-5 w-5 animate-spin text-accent" aria-hidden />
            ) : (
              <span className="h-5 w-5 rounded-full border border-neutral-300" />
            )}
            <span className={i === idx ? "font-semibold text-ink" : "text-ink-muted"}>{s.label}</span>
          </li>
        ))}
      </ol>
      {asyncMode && batchId ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          <span>Processing in background (up to 30 minutes per job policy).</span>
          <code className="rounded bg-surface-subtle px-2 py-0.5 font-mono text-xs">{batchId}</code>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs"
            onClick={copy}
          >
            <Copy className="h-3 w-3" />
            Copy
          </button>
        </div>
      ) : null}
    </div>
  );
}
