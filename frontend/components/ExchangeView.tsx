"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { citeLabel, docName, excerptBody, pageLabel, seconds, splitSection } from "@/lib/format";
import type { Exchange, Source } from "@/lib/types";
import RetrievalInspector from "./RetrievalInspector";
import Scores from "./Scores";

// Citation buttons read their state from context so the markdown renderer's
// component map stays stable; a new map per render would remount the buttons
// on hover and swallow clicks.
interface CiteState {
  byId: Record<string, Source>;
  active: string | null;
  setActive: (id: string | null) => void;
  onOpen: (s: Source) => void;
}
const CiteContext = createContext<CiteState | null>(null);

function CiteLink({ href, children }: { href?: string; children?: ReactNode }) {
  const ctx = useContext(CiteContext);
  if (!href?.startsWith("#cite-")) return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
  const s = ctx?.byId[href.slice(6)];
  if (!ctx || !s) return null;
  return (
    <button
      type="button"
      className="cite"
      aria-expanded={ctx.active === s.id}
      aria-label={`Source: ${s.section ?? "passage"}, ${pageLabel(s.page, s.page_end)}. Opens the PDF.`}
      onMouseEnter={() => ctx.setActive(s.id)}
      onMouseLeave={() => ctx.setActive(null)}
      onFocus={() => ctx.setActive(s.id)}
      onBlur={() => ctx.setActive(null)}
      onClick={() => ctx.onOpen(s)}
    >
      {children}
    </button>
  );
}

const MD_COMPONENTS: Components = { a: CiteLink };
const MD_PLUGINS = [remarkGfm];

function Note({ s, active, cited, collapsed = false, showDoc, onOpen }: {
  s: Source; active: boolean; cited: boolean; collapsed?: boolean; showDoc: boolean; onOpen: (s: Source) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const { num, title } = splitSection(s.section);
  const body = excerptBody(s.text, s.section);
  const long = body.length > 260;
  const hidden = collapsed && !expanded;
  return (
    <article className={`note${cited ? " cited" : " uncited"}${active ? " active" : ""}`} id={`note-${s.chunk_id}`}>
      <div className="note-head">
        {num && <span className="note-num">{num}</span>}
        <span className="note-title">{title}</span>
      </div>
      <div className="note-where">
        <button onClick={() => onOpen(s)}>Open {pageLabel(s.page, s.page_end).toLowerCase()}</button>
        {showDoc && <span>{docName(s.source)}</span>}
        {collapsed && (
          <button onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
            {expanded ? "Hide passage" : "Show passage"}
          </button>
        )}
      </div>
      {!hidden && (
        <>
          <p className={`excerpt${long && !expanded ? " clamped" : ""}`}>
            {cited ? <mark>{body}</mark> : body}
          </p>
          {long && !collapsed && (
            <button className="more" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
              {expanded ? "Show less" : "Show the whole passage"}
            </button>
          )}
        </>
      )}
    </article>
  );
}

export default function ExchangeView({ ex, multiDoc, onOpen }: {
  ex: Exchange; multiDoc: boolean; onOpen: (s: Source) => void;
}) {
  const [active, setActive] = useState<string | null>(null);
  const byId = useMemo(() => Object.fromEntries(ex.sources.map((s) => [s.id, s])), [ex.sources]);
  const streaming = ex.status === "answering";

  // [S2] -> a markdown link the renderer turns into a citation button labelled with the section number.
  const markdown = useMemo(() => {
    let text = ex.answer;
    if (streaming) text = text.replace(/\[S?\d*$/, "");
    return text.replace(/\[S(\d+)\]/g, (m, n) => {
      const s = byId[`S${n}`];
      return s ? `[${citeLabel(s.section, s.page)}](#cite-S${n})` : "";
    });
  }, [ex.answer, byId, streaming]);

  const citeState = useMemo<CiteState>(() => ({ byId, active, setActive, onOpen }), [byId, active, onOpen]);

  const done = ex.status === "done";
  const retrievalOnly = ex.mode === "retrieval_only";
  // While streaming, a source counts as cited as soon as its marker appears in the text.
  const streamedIds = useMemo(() => new Set(Array.from(ex.answer.matchAll(/\[S(\d+)\]/g), (m) => `S${m[1]}`)), [ex.answer]);
  const isCited = (s: Source) => (done ? s.cited : streamedIds.has(s.id));
  const cited = ex.sources.filter(isCited);
  const others = ex.sources.filter((s) => !isCited(s));
  const showMargin = !retrievalOnly && ex.sources.length > 0 && (done || ex.status === "answering");

  return (
    <div className="exchange" data-exchange={ex.id}>
      <h2 className="q">{ex.question}</h2>
      <div className="answer-col">
        {ex.status === "planning" && <p className="status-line"><span className="dots">Reading your question</span></p>}
        {ex.status === "retrieving" && <p className="status-line"><span className="dots">Searching the handbook</span></p>}

        {ex.plan?.route === "summary" && (
          <div className="plan-line">Summary of {ex.sources.length || "the most relevant"} passages, in the order the handbook presents them.</div>
        )}
        {ex.plan?.route === "multi_part" && (
          <div className="plan-line">
            This has {ex.plan.sub_questions.length} parts, so each was looked up separately:
            <ol>{ex.plan.sub_questions.map((q, i) => <li key={i}>{q}</li>)}</ol>
          </div>
        )}

        {ex.status === "error" ? (
          <p className="error-text" role="alert">{ex.error}</p>
        ) : (
          (ex.answer || streaming) && (
            <div className={`answer${streaming ? " streaming" : ""}`}>
              <CiteContext.Provider value={citeState}>
                <ReactMarkdown remarkPlugins={MD_PLUGINS} components={MD_COMPONENTS}>{markdown}</ReactMarkdown>
              </CiteContext.Provider>
            </div>
          )
        )}

        {done && ex.timings?.total_ms !== undefined && (
          <div className="meta">
            <span>Answered in {seconds(ex.timings.total_ms)}</span>
            {ex.plan?.planner === "rules" && <span>Planned by the rule-based fallback</span>}
            {!ex.options.rerank && ex.mode === "rag" && <span>Re-ranking off</span>}
          </div>
        )}

        {retrievalOnly && ex.sources.length > 0 && (
          <div className="passages-inline">
            {ex.sources.map((s) => <Note key={s.chunk_id} s={s} active={false} cited showDoc={multiDoc} onOpen={onOpen} />)}
          </div>
        )}

        {done && ex.eval && ex.mode === "rag" && <Scores initial={ex.eval} />}
        {done && ex.plan && ex.plan.route !== "chitchat" && ex.plan.route !== "out_of_scope" && ex.retrieval && (
          <RetrievalInspector plan={ex.plan} retrieval={ex.retrieval} timings={ex.timings} />
        )}
      </div>

      {showMargin && (
        <aside className="margin" aria-label="Sources for this answer">
          {cited.length > 0 && <p className="margin-title">Cited in this answer</p>}
          {cited.map((s) => <Note key={s.chunk_id} s={s} active={active === s.id} cited showDoc={multiDoc} onOpen={onOpen} />)}
          {done && others.length > 0 && (
            <>
              <p className="uncited-title">Also given to the model, not cited</p>
              {others.map((s) => <Note key={s.chunk_id} s={s} active={false} cited={false} collapsed showDoc={multiDoc} onOpen={onOpen} />)}
            </>
          )}
        </aside>
      )}
    </div>
  );
}
