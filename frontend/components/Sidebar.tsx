"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { docName, shortModel } from "@/lib/format";
import type { ChatOptions, DocInfo, Health } from "@/lib/types";
import { ExternalIcon, TrashIcon } from "./Icons";

interface Props {
  open: boolean;
  docs: DocInfo[];
  health: Health | null;
  options: ChatOptions;
  onOptions: (o: ChatOptions) => void;
  onDocs: (docs: DocInfo[]) => void;
}

export default function Sidebar({ open, docs, health, options, onOptions, onDocs }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  async function upload(files: File[]) {
    const pdfs = files.filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) {
      setError("Only PDF files can be added.");
      return;
    }
    setError(null);
    setBusy(pdfs.length === 1 ? `Reading ${pdfs[0].name}` : `Reading ${pdfs.length} files`);
    try {
      const res = await api.upload(pdfs);
      onDocs(res.documents);
      if (res.errors.length) setError(res.errors.map((e) => `${e.filename}: ${e.error}`).join(" "));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
      if (input.current) input.current.value = "";
    }
  }

  async function run(label: string, fn: () => Promise<{ documents: DocInfo[] }>) {
    setError(null);
    setBusy(label);
    try {
      onDocs((await fn()).documents);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const hasSample = docs.some((d) => d.is_sample);

  return (
    <aside className={`sidebar${open ? " open" : ""}`} aria-label="Handbooks and settings">
      <section className="side-section">
        <h2>Handbooks</h2>
        {!health ? (
          <p className="side-note" style={{ marginTop: 0 }}><span className="dots">Connecting to the server</span></p>
        ) : docs.length === 0 ? (
          <p className="side-note" style={{ marginTop: 0 }}>No handbook loaded. Add a PDF to start asking questions.</p>
        ) : (
          <ul className="doc-list">
            {docs.map((d) => (
              <li key={d.doc_id} className="doc">
                <span className="doc-name" title={d.filename}>
                  {docName(d.filename)}
                  {d.is_sample && <span className="tag">Sample</span>}
                </span>
                <span className="doc-meta">{d.pages} pages, {d.chunks} passages</span>
                <span className="doc-actions">
                  <a className="icon-btn" href={api.fileUrl(d.doc_id)} target="_blank" rel="noreferrer"
                     aria-label={`Open ${d.filename}`} title="Open PDF">
                    <ExternalIcon size={16} />
                  </a>
                  <button className="icon-btn" aria-label={`Remove ${d.filename}`} title="Remove"
                          disabled={!!busy} onClick={() => run("Removing", () => api.remove(d.doc_id))}>
                    <TrashIcon size={16} />
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}

        <div
          className={`dropzone${over ? " is-over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); upload(Array.from(e.dataTransfer.files)); }}
        >
          <button className="btn" onClick={() => input.current?.click()} disabled={!!busy || !health}>Add a PDF</button>
          <p>or drop handbook PDFs here, up to 25 MB each</p>
          <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden
                 onChange={(e) => upload(Array.from(e.target.files ?? []))} />
        </div>
        {health && !hasSample && (
          <button className="btn-quiet btn" style={{ marginTop: 6 }} disabled={!!busy}
                  onClick={() => run("Loading the sample", api.loadSample)}>
            Load the bundled handbooks
          </button>
        )}
        {busy && <p className="side-note" role="status"><span className="dots">{busy}</span></p>}
        {error && <p className="side-error" role="alert">{error}</p>}
      </section>

      <section className="side-section">
        <h2>Answer settings</h2>
        <label className="toggle">
          <input type="checkbox" checked={options.rerank}
                 onChange={(e) => onOptions({ ...options, rerank: e.target.checked })} />
          <span className="toggle-label">Re-rank passages</span>
          <span className="toggle-help">A cross-encoder re-orders the 12 closest passages before the best ones go to the model.</span>
        </label>
        <label className="toggle">
          <input type="checkbox" checked={options.evaluate} disabled={!!health && !health.eval_enabled}
                 onChange={(e) => onOptions({ ...options, evaluate: e.target.checked })} />
          <span className="toggle-label">Score answers with RAGAS</span>
          <span className="toggle-help">
            {!health || health.eval_enabled ? "Faithfulness, answer relevancy and context precision, scored in the background."
              : "Needs a Gemini API key."}
          </span>
        </label>
        <label className="toggle">
          <input type="checkbox" checked={options.retrieval_only || (!!health && !health.has_api_key)}
                 disabled={!!health && !health.has_api_key}
                 onChange={(e) => onOptions({ ...options, retrieval_only: e.target.checked })} />
          <span className="toggle-label">Show passages only</span>
          <span className="toggle-help">Skip the written answer and list the matching passages.</span>
        </label>
      </section>

      {health && (
        <section className="side-section">
          <h2>Models</h2>
          <dl className="system-list">
            <dt>Answers</dt><dd>{health.has_api_key ? shortModel(health.llm_model) : "off (no API key)"}</dd>
            <dt>Embeddings</dt><dd>{shortModel(health.embedding_model)}</dd>
            <dt>Re-ranker</dt><dd>{shortModel(health.reranker_model)}</dd>
            <dt>Judge</dt><dd>{health.eval_enabled ? shortModel(health.judge_model) : "off"}</dd>
          </dl>
        </section>
      )}
    </aside>
  );
}
