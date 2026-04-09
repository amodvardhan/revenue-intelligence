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
    <div className="surface-card p-5">
      <label htmlFor="nl-question" className="sr-only">
        Natural language question
      </label>
      <textarea
        id="nl-question"
        rows={5}
        className="w-full resize-y rounded-[10px] border border-black/[0.08] bg-surface-subtle px-4 py-3 text-[15px] text-ink placeholder:text-neutral-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
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
          className="btn-primary-solid gap-2 px-6 disabled:cursor-not-allowed"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
          Ask
        </button>
        <p className="text-[12px] text-ink-muted">Read-only, governed execution. ⌃↵ to submit.</p>
      </div>
    </div>
  );
}
