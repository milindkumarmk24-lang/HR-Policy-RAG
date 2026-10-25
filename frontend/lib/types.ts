export type Route = "policy_lookup" | "multi_part" | "summary" | "chitchat" | "out_of_scope";
export type Mode = "rag" | "direct" | "retrieval_only" | "no_documents";
export type EvalStatus = "queued" | "running" | "complete" | "partial" | "failed" | "skipped";

export interface Health {
  status: string;
  llm_model: string;
  judge_model: string;
  embedding_model: string;
  reranker_model: string | null;
  has_api_key: boolean;
  eval_enabled: boolean;
  documents: number;
  chunks: number;
  rpm_limit: number;
  eval_queue: number;
}

export interface DocInfo {
  doc_id: string;
  filename: string;
  pages: number;
  chunks: number;
  added_at: number;
  is_sample: boolean;
}

export interface Plan {
  route: Route;
  standalone_question: string;
  sub_questions: string[];
  topic: string;
  planner: "llm" | "rules";
}

export interface Source {
  id: string; // S1, S2...
  chunk_id: string;
  doc_id: string;
  source: string;
  page: number;
  page_end: number;
  section: string | null;
  chapter: string | null;
  category: string;
  text: string;
  faiss_rank: number;
  faiss_score: number;
  rerank_rank: number | null;
  rerank_score: number | null;
  relevance: number | null;
  selected: boolean;
  cited: boolean;
}

export interface CandidateSummary {
  chunk_id: string;
  doc_id: string;
  source: string;
  page: number;
  section: string | null;
  preview: string;
  faiss_rank: number;
  faiss_score: number;
  rerank_rank: number | null;
  rerank_score: number | null;
  relevance: number | null;
  selected: boolean;
}

export interface RetrievalSummary {
  reranked: boolean;
  fetch_k: number;
  sub_queries: { question: string; candidates: CandidateSummary[] }[];
}

export interface Scores {
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_precision: number | null;
}

export interface EvalInfo {
  query_id: string;
  eval_status: EvalStatus;
  scores: Scores | null;
  eval_error: string | Record<string, string> | null;
  eval_ms: number | null;
}

export interface ChatResult {
  query_id: string;
  question: string;
  answer: string;
  mode: Mode;
  plan: Plan;
  sources: Source[];
  retrieval: RetrievalSummary | null;
  timings: Record<string, number>;
  models: { llm: string | null; embedding: string; reranker: string | null; prompt_version: string };
  eval?: EvalInfo;
}

export interface EvalRecord {
  query_id: string;
  timestamp: string;
  question: string;
  standalone_question: string;
  route: Route;
  planner: string;
  sub_questions: string[];
  mode: Mode;
  answer: string;
  contexts: { id: string; chunk_id: string; source: string; page: number; section: string | null; cited: boolean; text: string }[];
  scores: Scores;
  eval_status: EvalStatus;
  eval_error: string | Record<string, string> | null;
  eval_ms: number | null;
  timings: Record<string, number> | null;
  models: Record<string, string | null>;
}

export interface EvalSummary {
  evaluated: number;
  total: number;
  pending: number;
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_precision: number | null;
}

export interface ChatOptions {
  rerank: boolean;
  evaluate: boolean;
  retrieval_only: boolean;
}

export interface Turn {
  role: "user" | "assistant";
  content: string;
}

/** One exchange in the conversation, built up while the answer streams. */
export interface Exchange {
  id: string;
  question: string;
  status: "planning" | "retrieving" | "answering" | "done" | "error";
  plan?: Plan;
  mode?: Mode;
  queryId?: string;
  sources: Source[];
  retrieval: RetrievalSummary | null;
  answer: string;
  timings?: Record<string, number>;
  eval?: EvalInfo;
  error?: string;
  options: ChatOptions;
}
