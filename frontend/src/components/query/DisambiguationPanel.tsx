import { AlertTriangle, Loader2 } from "lucide-react";

import type { ClarificationQuestion } from "@/types/query";

interface DisambiguationPanelProps {
  questions: ClarificationQuestion[];
  selections: Record<string, string>;
  onSelect: (promptId: string, choiceId: string) => void;
  onContinue: () => void;
  loading: boolean;
}

export function DisambiguationPanel({
  questions,
  selections,
  onSelect,
  onContinue,
  loading,
}: DisambiguationPanelProps) {
  const allAnswered = questions.every((q) => selections[q.prompt_id]);

  return (
    <div className="mt-4 rounded-md border border-border bg-surface-elevated p-4 shadow-sm">
      <div className="mb-3 flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden />
        <div>
          <h2 className="text-heading">Clarify your question</h2>
          <p className="text-small text-ink-muted">Choose an option so we do not guess financially material details.</p>
        </div>
      </div>
      <div className="space-y-4">
        {questions.map((q) => (
          <fieldset key={q.prompt_id} className="space-y-2">
            <legend className="text-sm font-medium text-ink">{q.text}</legend>
            <div className="flex flex-wrap gap-2">
              {q.choices.map((c) => (
                <label
                  key={c.id}
                  className={`cursor-pointer rounded-md border px-3 py-2 text-sm ${
                    selections[q.prompt_id] === c.id
                      ? "border-primary bg-primary-muted text-primary"
                      : "border-border bg-white hover:bg-neutral-50"
                  }`}
                >
                  <input
                    type="radio"
                    className="sr-only"
                    name={q.prompt_id}
                    checked={selections[q.prompt_id] === c.id}
                    onChange={() => onSelect(q.prompt_id, c.id)}
                  />
                  {c.label}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
      </div>
      <div className="mt-4">
        <button
          type="button"
          onClick={onContinue}
          disabled={!allAnswered || loading}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
          Continue
        </button>
      </div>
    </div>
  );
}
