import type { ChatOptions, ChatResult, DocInfo, EvalInfo, EvalRecord, EvalSummary, Health, Plan, Mode, RetrievalSummary, Source, Turn } from "./types";

/** Where the FastAPI backend lives. Empty string = same origin (production build served by FastAPI). */
export const API_BASE: string = (
  process.env.NEXT_PUBLIC_API_BASE ?? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "")
).replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error(`Can't reach the server at ${API_BASE || window.location.origin}. Is the backend running?`);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail ?? body?.errors?.[0]?.error ?? `Request failed (HTTP ${res.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  documents: () => request<{ documents: DocInfo[] }>("/api/documents"),
  upload: async (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const res = await fetch(`${API_BASE}/api/documents`, { method: "POST", body: form });
    const body = await res.json().catch(() => null);
    if (!body) throw new Error(`Upload failed (HTTP ${res.status})`);
    return body as { added: DocInfo[]; errors: { filename: string; error: string }[]; documents: DocInfo[] };
  },
  loadSample: () => request<{ documents: DocInfo[] }>("/api/documents/sample", { method: "POST" }),
  remove: (docId: string) => request<{ documents: DocInfo[] }>(`/api/documents/${docId}`, { method: "DELETE" }),
  evals: (limit = 100) => request<{ summary: EvalSummary; records: EvalRecord[] }>(`/api/evals?limit=${limit}`),
  evalStatus: (queryId: string) => request<EvalInfo>(`/api/evals/${queryId}`),
  retryEval: (queryId: string) => request<EvalInfo>(`/api/evals/${queryId}/retry`, { method: "POST" }),
  fileUrl: (docId: string, page?: number) => `${API_BASE}/api/documents/${docId}/file${page ? `#page=${page}` : ""}`,
  exportUrl: () => `${API_BASE}/api/evals/export`,
};

export interface StreamHandlers {
  onPlan: (d: { query_id: string; mode: Mode; plan: Plan }) => void;
  onRetrieval: (d: { sources: Source[]; retrieval: RetrievalSummary | null }) => void;
  onToken: (text: string) => void;
  onDone: (result: ChatResult) => void;
  onError: (message: string) => void;
}

/** POST /api/chat/stream and dispatch its server-sent events. */
export async function streamChat(question: string, history: Turn[], options: ChatOptions, h: StreamHandlers,
                                 signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history, options }),
      signal,
    });
  } catch (e) {
    if ((e as Error).name !== "AbortError") h.onError("Can't reach the server. Is the backend running?");
    return;
  }
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    h.onError(typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg ?? "Invalid request" : `Request failed (HTTP ${res.status})`);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const dispatch = (block: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) return;
    const payload = JSON.parse(data.join("\n"));
    if (event === "plan") h.onPlan(payload);
    else if (event === "retrieval") h.onRetrieval(payload);
    else if (event === "token") h.onToken(payload.text);
    else if (event === "done") h.onDone(payload);
    else if (event === "error") h.onError(payload.message);
  };
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        dispatch(buffer.slice(0, idx));
        buffer = buffer.slice(idx + 2);
      }
    }
    if (buffer.trim()) dispatch(buffer);
  } catch (e) {
    if ((e as Error).name !== "AbortError") h.onError("The connection dropped before the answer finished.");
  }
}
