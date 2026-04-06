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
    <div className="surface-card border-primary/10 p-5 shadow-glow">
      <label htmlFor="nl-question" className="sr-only">
        Natural language question
      </label>
      <textarea
        id="nl-question"
        rows={5}
        className="w-full resize-y rounded-xl border border-border/80 bg-surface-subtle/40 px-4 py-3 text-sm text-ink placeholder:text-ink-muted/60 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        placeholder="Example: What was Q3 revenue by business unit?"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled || loading}
        aria-busy={loading}
      />
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled || loading || !value.trim()}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-primary to-teal-500 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-teal-900/10 transition hover:brightness-105 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
          Ask
        </button>
        <p className="text-xs text-ink-muted">Read-only, governed execution. Ctrl+Enter to submit.</p>
      </div>
    </div>
  );
}
