"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "@/lib/api";
import { score, timeAgo } from "@/lib/format";
import type { EvalRecord, EvalSummary } from "@/lib/types";

const ROUTE: Record<string, string> = {
  policy_lookup: "Single", multi_part: "Multi-part", summary: "Summary", chitchat: "Small talk", out_of_scope: "Out of scope",
};
const STATUS: Record<string, string> = {
  complete: "Scored", partial: "Partly scored", failed: "Failed", skipped: "Not scored", queued: "Waiting", running: "Scoring",
};

export default function EvalLog() {
  const [data, setData] = useState<{ summary: EvalSummary; records: EvalRecord[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.evals(200));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  const s = data?.summary;
  return (
    <div className="evallog">
      <div className="evallog-head">
        <div>
          <h1>Evaluation log</h1>
          <p>
            Every answer is scored in the background with RAGAS, using Gemini as the judge, and appended to{" "}
            <code>data/logs/ragas_eval.jsonl</code>. Live questions have no reference answer, so these are the
            reference-free metrics.
          </p>
        </div>
        <div className="actions">
          <button className="btn" onClick={load}>Refresh</button>
          <a className="btn" href={api.exportUrl()} download>Download JSONL</a>
        </div>
      </div>

      {error && <p className="error-text" role="alert">{error}</p>}

      {s && (
        <div className="averages">
          <div><div className="avg-label">Answers scored</div><div className="avg-value">{s.evaluated}{s.pending ? ` (+${s.pending} pending)` : ""}</div></div>
          <div><div className="avg-label">Mean faithfulness</div><div className="avg-value">{score(s.faithfulness)}</div></div>
          <div><div className="avg-label">Mean answer relevancy</div><div className="avg-value">{score(s.answer_relevancy)}</div></div>
          <div><div className="avg-label">Mean context precision</div><div className="avg-value">{score(s.context_precision)}</div></div>
        </div>
      )}

      {data && data.records.length === 0 && (
        <div className="empty-state">No questions logged yet. Ask something in the Ask tab and its scores will appear here.</div>
      )}

      {data && data.records.length > 0 && (
        <table className="log-table">
          <thead>
            <tr>
              <th className="hide-sm">When</th>
              <th>Question</th>
              <th className="hide-sm">Route</th>
              <th className="num">Faithful.</th>
              <th className="num">Relevancy</th>
              <th className="num">Precision</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.records.map((r) => (
              <Fragment key={r.query_id}>
                <tr className="row" onClick={() => setOpen(open === r.query_id ? null : r.query_id)}
                    aria-expanded={open === r.query_id} tabIndex={0}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setOpen(open === r.query_id ? null : r.query_id))}>
                  <td className="hide-sm log-sub">{timeAgo(r.timestamp)}</td>
                  <td>
                    <div className="log-q">{r.question}</div>
                    {r.sub_questions.length > 1 && <div className="log-sub">{r.sub_questions.length} sub-questions</div>}
                  </td>
                  <td className="hide-sm">{ROUTE[r.route] ?? r.route}</td>
                  <td className="num">{score(r.scores?.faithfulness)}</td>
                  <td className="num">{score(r.scores?.answer_relevancy)}</td>
                  <td className="num">{score(r.scores?.context_precision)}</td>
                  <td>
                    <span className={`status-pill ${r.eval_status}`}
                          title={typeof r.eval_error === "string" ? r.eval_error : r.eval_error ? Object.values(r.eval_error).join("; ") : undefined}>
                      {STATUS[r.eval_status] ?? r.eval_status}
                    </span>
                  </td>
                </tr>
                {open === r.query_id && (
                  <tr className="log-detail">
                    <td colSpan={7}>
                      <div className="answer"><ReactMarkdown>{r.answer}</ReactMarkdown></div>
                      {r.contexts.length > 0 && (
                        <div className="ctx">
                          {r.contexts.map((c) => (
                            <div key={c.chunk_id} className={`note${c.cited ? " cited" : ""}`}>
                              <div className="note-where">
                                <span>[{c.id}] {c.section ?? "Passage"}, page {c.page}{c.cited ? ", cited" : ""}</span>
                              </div>
                              <p className="excerpt clamped">{c.text}</p>
                            </div>
                          ))}
                        </div>
                      )}
                      {r.eval_error && (
                        <p className="side-note">
                          {typeof r.eval_error === "string" ? r.eval_error : Object.entries(r.eval_error).map(([k, v]) => `${k}: ${v}`).join(" ")}
                        </p>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
