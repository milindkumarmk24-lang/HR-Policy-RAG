"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EvalInfo, Scores as ScoreSet } from "@/lib/types";

const METRICS: { key: keyof ScoreSet; name: string; help: string }[] = [
  { key: "faithfulness", name: "Faithfulness",
    help: "Share of the answer's claims that the cited passages actually support. Low means the answer says things the handbook excerpts don't." },
  { key: "answer_relevancy", name: "Answer relevancy",
    help: "How directly the answer addresses the question. RAGAS writes questions the answer would fit and compares them with yours." },
  { key: "context_precision", name: "Context precision",
    help: "Whether the passages that were useful for the answer were ranked at the top of what the model received." },
];

const PENDING = new Set(["queued", "running"]);

export default function Scores({ initial }: { initial: EvalInfo }) {
  const [info, setInfo] = useState<EvalInfo>(initial);

  useEffect(() => setInfo(initial), [initial]);

  useEffect(() => {
    if (!PENDING.has(info.eval_status)) return;
    let stopped = false;
    let tries = 0;
    const tick = async () => {
      if (stopped) return;
      tries += 1;
      try {
        const next = await api.evalStatus(info.query_id);
        if (!stopped) setInfo(next);
        if (PENDING.has(next.eval_status) && tries < 300) setTimeout(tick, 3000);
      } catch {
        if (tries < 300) setTimeout(tick, 5000);
      }
    };
    const t = setTimeout(tick, 2500);
    return () => { stopped = true; clearTimeout(t); };
  }, [info.query_id, info.eval_status]);

  if (info.eval_status === "skipped") return null;

  const pending = PENDING.has(info.eval_status);
  const failed = info.eval_status === "failed";
  return (
    <section className="scores" aria-live="polite">
      <div className="scores-head">
        <strong>RAGAS scores</strong>
        {pending && <span className="dots">{info.eval_status === "queued" ? "Waiting to score" : "Scoring"}</span>}
        {!pending && info.eval_ms !== null && <span>scored in {(info.eval_ms / 1000).toFixed(0)} s</span>}
        {(failed || info.eval_status === "partial") && (
          <button className="btn btn-quiet" style={{ padding: 0 }}
                  onClick={async () => setInfo(await api.retryEval(info.query_id))}>
            Score again
          </button>
        )}
      </div>
      <div className="score-grid">
        {METRICS.map((m) => {
          const v = info.scores?.[m.key] ?? null;
          return (
            <div key={m.key}>
              <div className="score-name">
                {m.name}
                <button className="help-tip" type="button" aria-label={`About ${m.name}`}>
                  ?<span className="tip" role="tooltip">{m.help}</span>
                </button>
              </div>
              <div className="score-val">
                {v === null ? <span className="score-empty">{pending ? "…" : "n/a"}</span> : v.toFixed(2)}
              </div>
              <div className="score-bar" aria-hidden="true">
                <span className={v !== null && v < 0.6 ? "low" : ""} style={{ width: `${(v ?? 0) * 100}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      {failed && (
        <p className="side-note">
          Scoring failed{typeof info.eval_error === "string" ? `: ${info.eval_error}` : "."} This is usually the Gemini rate limit; try again in a minute.
        </p>
      )}
    </section>
  );
}
