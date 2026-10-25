"use client";

import { citeLabel, splitSection } from "@/lib/format";
import type { CandidateSummary, Plan, RetrievalSummary } from "@/lib/types";
import { ChevronIcon } from "./Icons";

function trunc(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
}

/** Bump chart: where each candidate sat in FAISS order (left) and after re-ranking (right). */
function SlopeChart({ candidates }: { candidates: CandidateSummary[] }) {
  const k = candidates.length;
  const rowH = 22;
  const top = 30;
  const W = 600;
  const xL = 196;
  const xR = W - 196;
  const h = top + k * rowH + 4;
  const y = (rank: number) => top + (rank - 1) * rowH + rowH / 2;
  const label = (c: CandidateSummary) => {
    const { title } = splitSection(c.section);
    return `${citeLabel(c.section, c.page)} ${trunc(title, 24)}`;
  };
  return (
    <svg className="slope" viewBox={`0 0 ${W} ${h}`} role="img"
         aria-label="Rank of each passage before and after re-ranking. The table below lists the same data.">
      <text className="axis-title" x={xL} y={14} textAnchor="end">FAISS order</text>
      <text className="axis-title" x={xR} y={14}>After re-ranking</text>
      {candidates.map((c) => {
        const a = y(c.faiss_rank);
        const b = y(c.rerank_rank ?? c.faiss_rank);
        const sel = c.selected ? " sel" : "";
        return (
          <g key={c.chunk_id} className="row">
            <title>{`${c.section ?? "Passage"} (page ${c.page}): FAISS #${c.faiss_rank} → re-ranked #${c.rerank_rank}. ${c.preview}`}</title>
            <line className={`link${sel}`} x1={xL + 6} y1={a} x2={xR - 6} y2={b} />
            <circle className={sel.trim()} cx={xL + 6} cy={a} r={3.2} />
            <circle className={sel.trim()} cx={xR - 6} cy={b} r={3.2} />
            <text className={`lbl${sel}`} x={xL - 4} y={a + 4} textAnchor="end">{label(c)}</text>
            <text className={`lbl${sel}`} x={xR + 4} y={b + 4}>{label(c)}</text>
          </g>
        );
      })}
    </svg>
  );
}

function RankTable({ candidates, reranked }: { candidates: CandidateSummary[]; reranked: boolean }) {
  return (
    <table className="rank-table">
      <thead>
        <tr>
          <th>Passage</th>
          <th className="num">FAISS rank</th>
          <th className="num">Cosine</th>
          {reranked && <th className="num">Re-ranked</th>}
          {reranked && <th className="num">Relevance</th>}
        </tr>
      </thead>
      <tbody>
        {candidates.map((c) => {
          const move = reranked && c.rerank_rank ? c.faiss_rank - c.rerank_rank : 0;
          return (
            <tr key={c.chunk_id} className={c.selected ? "sel" : ""}>
              <td>
                {c.section ?? "Passage"}, page {c.page}
                {c.selected && <span className="sr-only"> (sent to the model)</span>}
              </td>
              <td className="num">{c.faiss_rank}</td>
              <td className="num">{c.faiss_score.toFixed(3)}</td>
              {reranked && (
                <td className="num">
                  {c.rerank_rank}{" "}
                  {move > 0 && <span className="move-up" aria-label={`up ${move}`}>+{move}</span>}
                  {move < 0 && <span className="move-down" aria-label={`down ${-move}`}>{move}</span>}
                </td>
              )}
              {reranked && <td className="num">{c.relevance === null ? "–" : c.relevance.toFixed(3)}</td>}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

const ROUTE_TEXT: Record<Plan["route"], string> = {
  policy_lookup: "Single policy question: one retrieval.",
  multi_part: "Multi-part question: split into sub-questions, each retrieved and re-ranked separately.",
  summary: "Summary request: a wider search (24 candidates), up to 10 passages kept and put back in handbook order.",
  chitchat: "Small talk: answered without searching the handbook.",
  out_of_scope: "Outside the handbook's scope: declined without searching.",
};

export default function RetrievalInspector({ plan, retrieval, timings }: {
  plan: Plan; retrieval: RetrievalSummary | null; timings?: Record<string, number>;
}) {
  return (
    <details className="inspect">
      <summary><ChevronIcon size={14} className="chev" />How this answer was found</summary>
      <div className="inspect-body">
        <h3>Route</h3>
        <p>
          {ROUTE_TEXT[plan.route]} {plan.planner === "rules" ? "Planned by the rule-based fallback." : "Planned by Gemini."}
          {plan.standalone_question && plan.route !== "chitchat" && (
            <> Searched for: <em>{plan.standalone_question}</em></>
          )}
        </p>
        {retrieval?.sub_queries.map((sq, i) => (
          <div className="subq" key={i}>
            <h3>{retrieval.sub_queries.length > 1 ? `Sub-question ${i + 1}: ${sq.question}` : "Retrieved passages"}</h3>
            <p>
              {retrieval.reranked
                ? `FAISS returned the ${sq.candidates.length} closest passages; the cross-encoder re-scored them. Highlighted rows were sent to the model.`
                : `Re-ranking was off, so passages stay in FAISS order. Highlighted rows were sent to the model.`}
            </p>
            {retrieval.reranked && <SlopeChart candidates={sq.candidates} />}
            <RankTable candidates={sq.candidates} reranked={retrieval.reranked} />
          </div>
        ))}
        {timings && (
          <p style={{ marginTop: 14, marginBottom: 0 }}>
            Timing: routing {((timings.route_ms ?? 0) / 1000).toFixed(1)} s, retrieval {((timings.retrieve_ms ?? 0) / 1000).toFixed(1)} s
            {timings.generate_ms !== undefined && `, generation ${(timings.generate_ms / 1000).toFixed(1)} s`}
            {timings.total_ms !== undefined && `, total ${(timings.total_ms / 1000).toFixed(1)} s`}.
          </p>
        )}
      </div>
    </details>
  );
}
