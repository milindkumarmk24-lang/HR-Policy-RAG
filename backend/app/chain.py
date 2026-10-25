"""The RAG pipeline, assembled with LCEL.

    question ─▶ router (plan + sub-questions) ─▶ retrieve per sub-question
             ─▶ cross-encoder re-rank ─▶ grounded prompt ─▶ Gemini ─▶ citations

`prepare` covers everything up to the prompt; `answer_chain` is
prompt | llm | parser. Splitting them lets the streaming endpoint send the
plan and the sources to the browser before the first answer token arrives.
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough

from .config import Settings
from .llm import LLMProvider
from .prompts import ANSWER_PROMPT, NOT_FOUND_TEXT, PROMPT_VERSION, SUMMARY_INSTRUCTIONS
from .retrieval import RetrievalResult, Retriever, candidate_to_source, format_context
from .router import QueryPlan, build_router, format_history

CITATION = re.compile(r"\[S(\d+)\]")
NO_DOCS_TEXT = ("No handbook is loaded yet. Upload an employee handbook PDF (or load the sample handbook) "
                "and ask again.")
NO_KEY_TEXT = ("Written answers are off because no Gemini API key is configured. These are the handbook passages "
               "the assistant would answer from, best match first.")
PASSAGES_ONLY_TEXT = "You asked for passages only. These are the best-matching handbook passages, best match first."


@dataclass
class ChatOptions:
    rerank: bool = True
    top_n: int | None = None
    evaluate: bool = True
    retrieval_only: bool = False


@dataclass
class Prepared:
    query_id: str
    question: str
    history: list[dict]
    options: ChatOptions
    plan: QueryPlan
    retrieval: RetrievalResult | None
    prompt_inputs: dict | None
    mode: str                       # rag | direct | retrieval_only | no_documents
    timings: dict = field(default_factory=dict)
    started: float = field(default_factory=time.perf_counter)


class RAGPipeline:
    def __init__(self, settings: Settings, llm_provider: LLMProvider, retriever: Retriever):
        self.settings = settings
        self.retriever = retriever
        self.llm_provider = llm_provider
        self.llm = llm_provider.chat_model() if llm_provider.available else None
        router_llm = llm_provider.chat_model(temperature=0, max_output_tokens=1024) if self.llm else None
        self.router: Runnable = build_router(router_llm)
        self.answer_chain: Runnable | None = (ANSWER_PROMPT | self.llm | StrOutputParser()) if self.llm else None

        # LCEL "prepare" chain: each step adds one key to the running dict.
        self.prepare_chain: Runnable = (
            RunnablePassthrough.assign(plan=RunnableLambda(self._plan))
            | RunnablePassthrough.assign(retrieval=RunnableLambda(self._retrieve))
            | RunnablePassthrough.assign(prompt_inputs=RunnableLambda(self._prompt_inputs))
        )

    # ------------------------------------------------------------ steps --
    async def _plan(self, x: dict) -> QueryPlan:
        t0 = time.perf_counter()
        plan = await self.router.ainvoke({"question": x["question"], "history": x["history"]})
        x["timings"]["route_ms"] = _ms(t0)
        return plan

    async def _retrieve(self, x: dict) -> RetrievalResult | None:
        plan: QueryPlan = x["plan"]
        if not plan.needs_retrieval or self.retriever.index.is_empty:
            return None
        opts: ChatOptions = x["options"]
        t0 = time.perf_counter()
        if plan.route == "summary":
            result = await asyncio.to_thread(self.retriever.retrieve_summary, plan.sub_questions[0], opts.rerank)
        else:
            result = await asyncio.to_thread(self.retriever.retrieve, plan.sub_questions, opts.rerank, opts.top_n)
        x["timings"]["retrieve_ms"] = _ms(t0)
        return result

    @staticmethod
    def _prompt_inputs(x: dict) -> dict | None:
        retrieval: RetrievalResult | None = x["retrieval"]
        if retrieval is None or not retrieval.context:
            return None
        plan: QueryPlan = x["plan"]
        instructions = ""
        if plan.route == "multi_part":
            instructions = ("Parts to answer:\n"
                            + "\n".join(f"{i}. {q}" for i, q in enumerate(plan.sub_questions, 1)) + "\n")
        elif plan.route == "summary":
            instructions = SUMMARY_INSTRUCTIONS
        return {
            "history": format_history(x["history"]),
            "question": plan.standalone_question,
            "instructions": instructions,
            "context": format_context(retrieval.context),
        }

    # ----------------------------------------------------------- public --
    async def prepare(self, question: str, history: list[dict] | None = None,
                      options: ChatOptions | None = None) -> Prepared:
        options = options or ChatOptions()
        state = {"question": question.strip(), "history": history or [], "options": options, "timings": {}}
        started = time.perf_counter()
        out = await self.prepare_chain.ainvoke(state)
        plan: QueryPlan = out["plan"]
        if not plan.needs_retrieval:
            mode = "direct"
        elif self.retriever.index.is_empty:
            mode = "no_documents"
        elif options.retrieval_only or self.answer_chain is None:
            mode = "retrieval_only"
        else:
            mode = "rag"
        return Prepared(query_id=uuid.uuid4().hex[:12], question=state["question"], history=state["history"],
                        options=options, plan=plan, retrieval=out["retrieval"],
                        prompt_inputs=out["prompt_inputs"], mode=mode, timings=out["timings"], started=started)

    def fixed_answer(self, p: Prepared) -> str | None:
        """Answers that need no generation call."""
        if p.mode == "direct":
            return p.plan.direct_reply or ""
        if p.mode == "no_documents":
            return NO_DOCS_TEXT
        if p.mode == "retrieval_only":
            return NO_KEY_TEXT if self.answer_chain is None else PASSAGES_ONLY_TEXT
        if p.prompt_inputs is None:
            return NOT_FOUND_TEXT
        return None

    async def stream_answer(self, p: Prepared) -> AsyncIterator[str]:
        fixed = self.fixed_answer(p)
        if fixed is not None:
            yield fixed
            return
        t0 = time.perf_counter()
        first = True
        async for token in self.answer_chain.astream(p.prompt_inputs):
            if first:
                p.timings["first_token_ms"] = _ms(t0)
                first = False
            if token:
                yield token
        p.timings["generate_ms"] = _ms(t0)

    async def answer(self, p: Prepared) -> str:
        fixed = self.fixed_answer(p)
        if fixed is not None:
            return fixed
        t0 = time.perf_counter()
        text = await self.answer_chain.ainvoke(p.prompt_inputs)
        p.timings["generate_ms"] = _ms(t0)
        return text

    def finalize(self, p: Prepared, answer: str) -> dict:
        """Build the API response: validate citations and attach sources."""
        context = p.retrieval.context if p.retrieval else []
        valid = {str(i) for i in range(1, len(context) + 1)}
        # Drop citations to sources that don't exist (the model occasionally invents [S9]).
        answer = CITATION.sub(lambda m: m.group(0) if m.group(1) in valid else "", answer).strip()
        cited = {int(n) for n in CITATION.findall(answer)}
        sources = []
        for i, c in enumerate(context, start=1):
            s = candidate_to_source(c, i)
            s["cited"] = i in cited
            sources.append(s)
        p.timings["total_ms"] = _ms(p.started)
        return {
            "query_id": p.query_id,
            "question": p.question,
            "answer": answer,
            "mode": p.mode,
            "plan": {
                "route": p.plan.route,
                "standalone_question": p.plan.standalone_question,
                "sub_questions": p.plan.sub_questions,
                "topic": p.plan.topic,
                "planner": p.plan.planner,
            },
            "sources": sources,
            "retrieval": p.retrieval.summary() if p.retrieval else None,
            "timings": p.timings,
            "models": {
                "llm": self.settings.gemini_model if self.llm else None,
                "embedding": self.settings.embedding_model,
                "reranker": self.settings.reranker_model if (p.retrieval and p.retrieval.reranked) else None,
                "prompt_version": PROMPT_VERSION,
            },
        }

    async def run(self, question: str, history: list[dict] | None = None,
                  options: ChatOptions | None = None) -> dict:
        p = await self.prepare(question, history, options)
        return self.finalize(p, await self.answer(p))


def strip_citations(text: str) -> str:
    return re.sub(r"\s*\[S\d+\]", "", text).strip()


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)
