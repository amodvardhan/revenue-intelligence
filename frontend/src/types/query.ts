/** Phase 3 NL query API shapes (aligned with api-contracts §8). */

export interface ClarificationChoice {
  id: string;
  label: string;
}

export interface ClarificationQuestion {
  prompt_id: string;
  text: string;
  choices: ClarificationChoice[];
}

export interface NaturalLanguageRequest {
  question: string;
  org_id?: string;
  disambiguation_token?: string;
  clarifications?: Array<{ prompt_id: string; choice: string }>;
}

export interface NaturalLanguageResponseCompleted {
  query_id: string;
  status: "completed";
  interpretation: string;
  columns: string[];
  rows: Record<string, string | null | undefined>[];
  disambiguation: null;
  semantic_version_label: string;
}

export interface NaturalLanguageResponseClarify {
  query_id: string;
  status: "needs_clarification";
  questions: ClarificationQuestion[];
  disambiguation: { token: string };
  semantic_version_label?: string;
}

export type NaturalLanguageResponse =
  | NaturalLanguageResponseCompleted
  | NaturalLanguageResponseClarify;

export interface AuditListItem {
  log_id: string;
  user_id: string | null;
  natural_query: string;
  status: string | null;
  row_count: number | null;
  execution_ms: number | null;
  created_at: string;
  correlation_id: string | null;
}

export interface AuditListResponse {
  items: AuditListItem[];
  next_cursor: string | null;
}
