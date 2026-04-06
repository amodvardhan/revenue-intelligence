import { useMutation } from "@tanstack/react-query";
import axios from "axios";
import { useCallback, useState, type KeyboardEvent } from "react";

import { DisambiguationPanel } from "@/components/query/DisambiguationPanel";
import { NLQueryComposer } from "@/components/query/NLQueryComposer";
import { NLQueryResultPanel } from "@/components/query/NLQueryResultPanel";
import { NLQuerySafetyMessage } from "@/components/query/NLQuerySafetyMessage";
import { ResolvedInterpretationPanel } from "@/components/query/ResolvedInterpretationPanel";
import { api } from "@/services/api";
import type {
  ClarificationQuestion,
  NaturalLanguageRequest,
  NaturalLanguageResponse,
  NaturalLanguageResponseCompleted,
} from "@/types/query";

function isCompleted(r: NaturalLanguageResponse): r is NaturalLanguageResponseCompleted {
  return r.status === "completed";
}

function apiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err) && err.response?.data && typeof err.response.data === "object") {
    const d = err.response.data as { error?: { message?: string } };
    if (d.error?.message) return d.error.message;
  }
  return err instanceof Error ? err.message : "Request failed";
}

export function NLQueryPage() {
  const [question, setQuestion] = useState("");
  const [orgId, setOrgId] = useState("");
  const [disambiguationToken, setDisambiguationToken] = useState<string | null>(null);
  const [clarifyQuestions, setClarifyQuestions] = useState<ClarificationQuestion[]>([]);
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [completed, setCompleted] = useState<NaturalLanguageResponseCompleted | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (body: NaturalLanguageRequest) => {
      const { data } = await api.post<NaturalLanguageResponse>("/api/v1/query/natural-language", body);
      return data;
    },
    onSuccess: (data) => {
      setClientError(null);
      if (data.status === "needs_clarification") {
        setDisambiguationToken(data.disambiguation.token);
        setClarifyQuestions(data.questions);
        setSelections({});
        setCompleted(null);
        return;
      }
      if (isCompleted(data)) {
        setCompleted(data);
        setDisambiguationToken(null);
        setClarifyQuestions([]);
      }
    },
    onError: (err) => {
      setClientError(apiErrorMessage(err));
      setCompleted(null);
    },
  });

  const runAsk = useCallback(() => {
    const body: NaturalLanguageRequest = {
      question: question.trim(),
      ...(orgId ? { org_id: orgId } : {}),
    };
    if (disambiguationToken) {
      body.disambiguation_token = disambiguationToken;
      body.clarifications = Object.entries(selections).map(([prompt_id, choice]) => ({
        prompt_id,
        choice,
      }));
    }
    mutation.mutate(body);
  }, [question, orgId, disambiguationToken, selections, mutation]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      runAsk();
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-display text-2xl font-semibold text-slate-900">Ask revenue</h1>
      <p className="mt-1 text-small text-slate-600">
        Ask questions in plain language. Answers use the same revenue definitions as Analytics — governed,
        read-only execution.
      </p>

      <div className="mt-6 max-w-3xl space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-700">
            Organization (optional)
            <input
              type="text"
              className="ml-2 w-72 rounded-sm border border-border px-2 py-1 font-mono text-xs"
              placeholder="org UUID"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value.trim())}
              disabled={mutation.isPending}
            />
          </label>
        </div>

        <NLQueryComposer
          value={question}
          onChange={setQuestion}
          onSubmit={runAsk}
          onKeyDown={onKeyDown}
          loading={mutation.isPending}
        />

        {clientError ? (
          <NLQuerySafetyMessage title="Could not complete request" message={clientError} variant="error" />
        ) : null}

        {clarifyQuestions.length > 0 && disambiguationToken ? (
          <DisambiguationPanel
            questions={clarifyQuestions}
            selections={selections}
            onSelect={(promptId, choiceId) =>
              setSelections((s) => ({
                ...s,
                [promptId]: choiceId,
              }))
            }
            onContinue={runAsk}
            loading={mutation.isPending}
          />
        ) : null}

        {completed ? (
          <>
            <ResolvedInterpretationPanel interpretation={completed.interpretation} />
            <p className="text-xs text-slate-500">Semantic version: {completed.semantic_version_label}</p>
            <NLQueryResultPanel columns={completed.columns} rows={completed.rows} />
          </>
        ) : null}
      </div>
    </div>
  );
}
