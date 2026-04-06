import type { KeyboardEvent } from "react";
import { Loader2 } from "lucide-react";

interface NLQueryComposerProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onKeyDown?: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  loading: boolean;
  disabled?: boolean;
}

export function NLQueryComposer({
  value,
  onChange,
  onSubmit,
  onKeyDown,
  loading,
  disabled,
}: NLQueryComposerProps) {
  return (
    <div className="rounded-md border border-border bg-surface-elevated p-4 shadow-sm">
      <label htmlFor="nl-question" className="sr-only">
        Natural language question
      </label>
      <textarea
        id="nl-question"
        rows={4}
        className="w-full resize-y rounded-sm border border-border px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary"
        placeholder="Example: What was Q3 revenue by business unit?"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled || loading}
        aria-busy={loading}
      />
      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled || loading || !value.trim()}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
          Ask
        </button>
        <p className="text-xs text-slate-500">Read-only, governed execution. Ctrl+Enter to submit.</p>
      </div>
    </div>
  );
}
