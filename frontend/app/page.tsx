"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Composer from "@/components/Composer";
import EvalLog from "@/components/EvalLog";
import ExchangeView from "@/components/ExchangeView";
import { BookIcon, MoonIcon, SunIcon } from "@/components/Icons";
import PdfDrawer from "@/components/PdfDrawer";
import Sidebar from "@/components/Sidebar";
import { API_BASE, api, streamChat } from "@/lib/api";
import { docName } from "@/lib/format";
import type { ChatOptions, DocInfo, Exchange, Health, Source, Turn } from "@/lib/types";

const SAMPLE_QUESTIONS = [
  { topic: "Leave", q: "How many sick days do I get, and when do I need a medical certificate?" },
  { topic: "Travel", q: "What are the hotel limit and per diem for a trip to Mumbai?" },
  { topic: "Two questions at once", q: "Can I carry forward casual leave, and what is the notice period at level L3?" },
  { topic: "Conduct", q: "How do I raise a sexual harassment complaint, and is there a time limit?" },
  { topic: "Summary", q: "Give me an overview of the leave policy." },
  { topic: "Not in the handbook", q: "Does the company offer a car lease scheme?" },
];
const GENERIC_QUESTIONS = [
  { topic: "Leave", q: "How much paid leave do I get each year?" },
  { topic: "Benefits", q: "What does the health insurance cover?" },
  { topic: "Separation", q: "What is the notice period if I resign?" },
  { topic: "Conduct", q: "Can I accept gifts from clients or vendors?" },
];

const IS_LOCAL_API = !API_BASE || /localhost|127\.0\.0\.1/.test(API_BASE);

function historyFrom(exchanges: Exchange[]): Turn[] {
  return exchanges
    .filter((e) => e.status === "done" && e.mode !== "retrieval_only")
    .slice(-3)
    .flatMap((e) => [{ role: "user" as const, content: e.question }, { role: "assistant" as const, content: e.answer }]);
}

export default function Home() {
  const [tab, setTab] = useState<"ask" | "log">("ask");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [options, setOptions] = useState<ChatOptions>({ rerank: true, evaluate: true, retrieval_only: false });
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [drawer, setDrawer] = useState<Source | null>(null);
  const [sideOpen, setSideOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);
  const [systemDark, setSystemDark] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
      setHealthError(null);
    } catch (e) {
      setHealthError((e as Error).message);
    }
  }, []);

  // Connect to the backend, retrying for a few minutes: a hosted backend that
  // scales to zero needs 20-60 seconds to start on the first request.
  useEffect(() => {
    let cancelled = false;
    const slow = setTimeout(() => !cancelled && setConnecting(true), 2500);
    (async () => {
      for (let attempt = 0; attempt < 36 && !cancelled; attempt++) {
        try {
          const h = await api.health();
          if (cancelled) return;
          setHealth(h);
          setHealthError(null);
          const d = await api.documents();
          if (!cancelled) setDocs(d.documents);
          break;
        } catch (e) {
          if (cancelled) return;
          if (attempt >= 2) setHealthError((e as Error).message);
          await new Promise((r) => setTimeout(r, 5000));
        }
      }
      clearTimeout(slow);
      if (!cancelled) setConnecting(false);
    })();
    return () => { cancelled = true; clearTimeout(slow); };
  }, []);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("theme");
      if (saved === "light" || saved === "dark") setTheme(saved);
    } catch { /* storage unavailable */ }
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (mq) {
      setSystemDark(mq.matches);
      const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
  }, []);

  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }, [theme]);

  // Bring each new question to the top of the view; the answer streams in below it.
  const lastId = exchanges[exchanges.length - 1]?.id;
  useEffect(() => {
    if (!lastId) return;
    const el = scroller.current?.querySelector(`[data-exchange="${lastId}"]`);
    el?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [lastId]);

  const update = (id: string, patch: Partial<Exchange> | ((e: Exchange) => Partial<Exchange>)) =>
    setExchanges((list) => list.map((e) => (e.id === id ? { ...e, ...(typeof patch === "function" ? patch(e) : patch) } : e)));

  async function ask(question: string) {
    const id = typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const opts = { ...options, retrieval_only: options.retrieval_only || !health?.has_api_key };
    const history = historyFrom(exchanges);
    setExchanges((list) => [...list, { id, question, status: "planning", sources: [], retrieval: null, answer: "", options: opts }]);
    const ctrl = new AbortController();
    abort.current = ctrl;
    await streamChat(question, history, opts, {
      onPlan: (d) => update(id, { plan: d.plan, mode: d.mode, queryId: d.query_id, status: "retrieving" }),
      onRetrieval: (d) => update(id, { sources: d.sources, retrieval: d.retrieval, status: "answering" }),
      onToken: (t) => update(id, (e) => ({ answer: e.answer + t })),
      onDone: (r) => update(id, { status: "done", answer: r.answer, sources: r.sources, retrieval: r.retrieval,
                                  plan: r.plan, mode: r.mode, timings: r.timings, eval: r.eval }),
      onError: (message) => update(id, { status: "error", error: message }),
    }, ctrl.signal);
    abort.current = null;
    setExchanges((list) => list.map((e) => e.id === id && e.status !== "done" && e.status !== "error"
      ? { ...e, status: "error", error: e.answer ? "Stopped." : "Stopped before an answer arrived." } : e));
  }

  const busy = exchanges.some((e) => e.status !== "done" && e.status !== "error");
  const onDocs = (d: DocInfo[]) => { setDocs(d); refreshHealth(); };
  const onlySample = docs.length > 0 && docs.every((d) => d.is_sample);
  const suggestions = onlySample ? SAMPLE_QUESTIONS : GENERIC_QUESTIONS;
  const effectiveDark = theme ? theme === "dark" : systemDark;
  const closeDrawer = useCallback(() => setDrawer(null), []);

  function toggleTheme() {
    const next = effectiveDark ? "light" : "dark";
    setTheme(next);
    try { localStorage.setItem("theme", next); } catch { /* ignore */ }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <button className="icon-btn docs-toggle" aria-label="Handbooks and settings" aria-expanded={sideOpen}
                onClick={() => setSideOpen((v) => !v)}>
          <BookIcon />
        </button>
        <div className="wordmark">
          <span className="wordmark-mark" aria-hidden="true">§</span>
          <span className="wordmark-text">HR Policy Bot</span>
        </div>
        <nav className="tabs" role="tablist" aria-label="Views">
          <button role="tab" className="tab" aria-selected={tab === "ask"} onClick={() => setTab("ask")}>Ask</button>
          <button role="tab" className="tab" aria-selected={tab === "log"} onClick={() => setTab("log")}>Evaluation log</button>
        </nav>
        <div className="topbar-end">
          <button className="icon-btn" onClick={toggleTheme} aria-label={effectiveDark ? "Use light theme" : "Use dark theme"}>
            {effectiveDark ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      <Sidebar open={sideOpen} docs={docs} health={health} options={options} onOptions={setOptions} onDocs={onDocs} />

      <main className="main" onClick={() => sideOpen && setSideOpen(false)}>
        {tab === "log" ? (
          <div className="scroll"><EvalLog /></div>
        ) : (
          <>
            <div className="scroll" ref={scroller}>
              {!health && connecting && !healthError && (
                <div className="notice" role="status">
                  <strong className="dots">Starting the server</strong>
                  <p>The hosted backend sleeps when nobody is using it and takes up to a minute to wake up. This page connects on its own.</p>
                </div>
              )}
              {!health && healthError && (
                <div className="notice" role="alert">
                  <strong>Can&apos;t reach the backend yet.</strong>
                  {IS_LOCAL_API ? (
                    <p>{healthError} Start it with <code>uvicorn app.main:app --port 8000</code> in the backend folder; this page keeps retrying.</p>
                  ) : (
                    <p>It may still be starting up (this page keeps retrying for a few minutes). If this persists, the backend at <code>{API_BASE}</code> is down.</p>
                  )}
                </div>
              )}
              {health && !health.has_api_key && (
                <div className="notice">
                  <strong>Written answers are off until a Gemini API key is added.</strong>
                  <p>You can still search the handbook: you&apos;ll see the passages the bot would answer from. To turn answers
                    and RAGAS scoring on, put <code>GOOGLE_API_KEY=...</code> in <code>backend/.env</code> and restart the server.</p>
                </div>
              )}
              {exchanges.length === 0 ? (
                <div className="welcome">
                  <h1>Ask your employee handbook.</h1>
                  <p>
                    {!health ? "Connecting to the server…" : docs.length
                      ? `Answers come from ${docs.length === 1 ? docName(docs[0].filename) : `${docs.length} handbooks`}, with the section and page they're based on, so you can check the original.`
                      : "Add a handbook PDF on the left, or load the bundled handbooks, then ask a question."}
                  </p>
                  {docs.length > 0 && (
                    <ul className="suggestions">
                      {suggestions.map((s) => (
                        <li key={s.q}>
                          <button onClick={() => ask(s.q)} disabled={busy}>
                            <span className="sugg-topic">{s.topic}</span>{s.q}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <div className="thread">
                  {exchanges.map((ex) => <ExchangeView key={ex.id} ex={ex} multiDoc={docs.length > 1} onOpen={setDrawer} />)}
                </div>
              )}
            </div>
            <Composer busy={busy} disabled={docs.length === 0} onSend={ask} onStop={() => abort.current?.abort()} />
          </>
        )}
      </main>

      <PdfDrawer source={drawer} onClose={closeDrawer} />
    </div>
  );
}
