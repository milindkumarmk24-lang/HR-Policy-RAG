"""Per-query RAGAS evaluation, run in the background and logged to JSONL.

Live questions have no ground-truth answer, so each query is scored with three
reference-free RAGAS metrics, using Gemini as the judge:

- faithfulness: share of the answer's claims that the retrieved chunks support.
- answer_relevancy: how well the answer addresses the question (RAGAS writes
  questions the answer would fit, then compares them to the real one using our
  local embeddings).
- context_precision: whether the chunks that were useful for the answer are
  ranked near the top (LLMContextPrecisionWithoutReference).

Scoring takes ~10 judge calls, so it never blocks the answer: the chat
endpoint returns immediately and the UI polls /api/evals/{query_id}.
The offline golden-set script (eval/run_golden.py) adds the reference-based
metrics (context recall, context precision with reference).
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import warnings
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .llm import LLMProvider

log = logging.getLogger(__name__)

LIVE_METRICS = ("faithfulness", "answer_relevancy", "context_precision")


class RagasScorer:
    """Thin wrapper that owns the judge LLM and the RAGAS metric objects."""

    def __init__(self, settings: Settings, llm_provider: LLMProvider, embeddings, with_reference: bool = False):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from ragas.embeddings import LangchainEmbeddingsWrapper
            from ragas.llms import LangchainLLMWrapper
            from ragas.metrics import (
                Faithfulness,
                LLMContextPrecisionWithoutReference,
                LLMContextPrecisionWithReference,
                LLMContextRecall,
                ResponseRelevancy,
            )
            from ragas.run_config import RunConfig

            self.run_config = RunConfig(timeout=180, max_retries=6, max_wait=60, max_workers=2)
            judge = llm_provider.chat_model(model=settings.judge_model_name, temperature=0,
                                            max_output_tokens=4096, max_retries=6)
            # bypass_n: ask for several generations as separate calls instead of
            # candidate_count, which not every Gemini model accepts.
            self.llm = LangchainLLMWrapper(judge, run_config=self.run_config, bypass_n=True)
            self.embeddings = LangchainEmbeddingsWrapper(embeddings)
            self.metrics: dict[str, Any] = {
                "faithfulness": Faithfulness(llm=self.llm),
                "answer_relevancy": ResponseRelevancy(llm=self.llm, embeddings=self.embeddings,
                                                      strictness=settings.answer_relevancy_strictness),
                "context_precision": LLMContextPrecisionWithoutReference(llm=self.llm),
            }
            if with_reference:
                self.metrics["context_precision_ref"] = LLMContextPrecisionWithReference(llm=self.llm)
                self.metrics["context_recall"] = LLMContextRecall(llm=self.llm)
            for m in self.metrics.values():
                m.init(self.run_config)
        self.judge_model = settings.judge_model_name

    async def score(self, question: str, answer: str, contexts: list[str], reference: str | None = None,
                    metric_names: tuple[str, ...] | None = None, before_each=None) -> tuple[dict, dict]:
        from ragas.dataset_schema import SingleTurnSample

        sample = SingleTurnSample(user_input=question, response=answer, retrieved_contexts=contexts,
                                  reference=reference)
        scores: dict[str, float | None] = {}
        errors: dict[str, str] = {}
        for name in metric_names or tuple(self.metrics):
            if before_each is not None:
                await before_each()
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    value = await self.metrics[name].single_turn_ascore(sample, timeout=self.run_config.timeout)
                value = float(value)
                if math.isnan(value):
                    scores[name] = None
                    errors[name] = "RAGAS returned NaN (e.g. the answer contained no checkable claims)"
                else:
                    scores[name] = round(value, 4)
            except Exception as e:  # rate limits, timeouts, malformed judge output
                log.warning("RAGAS %s failed: %s", name, e)
                scores[name] = None
                errors[name] = f"{type(e).__name__}: {str(e)[:300]}"
        return scores, errors


class EvalService:
    """Queues finished answers, scores them one at a time, and appends each
    record to data/logs/ragas_eval.jsonl (see to_log_line for the format)."""

    def __init__(self, settings: Settings, llm_provider: LLMProvider, embeddings):
        self.settings = settings
        self.llm_provider = llm_provider
        self.log_path: Path = settings.eval_log_path
        self.enabled = settings.eval_enabled and llm_provider.available
        self._embeddings = embeddings
        self._scorer: RagasScorer | None = None
        self.records: dict[str, dict] = {}
        self.order: deque[str] = deque(maxlen=500)
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._load_history()

    # --------------------------------------------------------- lifecycle --
    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run(), name="ragas-eval-worker")

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    def _load_history(self, limit: int = 200) -> None:
        if not self.log_path.exists():
            return
        lines = self.log_path.read_text(encoding="utf-8").splitlines()[-limit:]
        for line in lines:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "scores" not in rec:
                rec["scores"] = {k: (rec.get("metrics") or {}).get(k) for k in LIVE_METRICS}
            rec.pop("metrics", None)
            rec.pop("answer_preview", None)
            self.records[rec["query_id"]] = rec
            self.order.append(rec["query_id"])

    @property
    def scorer(self) -> RagasScorer:
        if self._scorer is None:
            self._scorer = RagasScorer(self.settings, self.llm_provider, self._embeddings)
        return self._scorer

    # ------------------------------------------------------------- api --
    def submit(self, result: dict, evaluate: bool = True) -> dict:
        rec = self._make_record(result)
        if result["mode"] != "rag":
            rec["eval_status"] = "skipped"
            rec["eval_error"] = {"direct": "No retrieval for this route",
                                 "no_documents": "No documents indexed",
                                 "retrieval_only": "No answer was generated"}.get(result["mode"], result["mode"])
        elif not self.enabled:
            rec["eval_status"] = "skipped"
            rec["eval_error"] = ("Evaluation disabled (EVAL_ENABLED=false)" if self.llm_provider.available
                                 else "No GOOGLE_API_KEY configured")
        elif not evaluate:
            rec["eval_status"] = "skipped"
            rec["eval_error"] = "Evaluation turned off for this query"
        else:
            rec["eval_status"] = "queued"
        self._remember(rec)
        if rec["eval_status"] == "queued":
            self.queue.put_nowait(rec["query_id"])
        else:
            self._append(rec)
        return self.public(rec)

    def retry(self, query_id: str) -> dict | None:
        rec = self.records.get(query_id)
        if rec is None or rec.get("mode") != "rag" or not self.enabled:
            return None
        if rec["eval_status"] in ("queued", "running"):
            return self.public(rec)
        rec.update(eval_status="queued", eval_error=None, scores={k: None for k in LIVE_METRICS})
        self.queue.put_nowait(query_id)
        return self.public(rec)

    def get(self, query_id: str) -> dict | None:
        rec = self.records.get(query_id)
        return self.public(rec) if rec else None

    def recent(self, limit: int = 50) -> list[dict]:
        ids = list(self.order)[-limit:][::-1]
        return [self.records[i] for i in ids if i in self.records]

    def aggregate(self) -> dict:
        done = [r for r in self.records.values() if r.get("eval_status") in ("complete", "partial")]
        agg: dict[str, Any] = {"evaluated": len(done), "total": len(self.records),
                               "pending": sum(1 for r in self.records.values()
                                              if r.get("eval_status") in ("queued", "running"))}
        for m in LIVE_METRICS:
            vals = [r["scores"][m] for r in done if r.get("scores", {}).get(m) is not None]
            agg[m] = round(sum(vals) / len(vals), 4) if vals else None
        return agg

    @staticmethod
    def public(rec: dict) -> dict:
        return {"query_id": rec["query_id"], "eval_status": rec["eval_status"], "scores": rec.get("scores"),
                "eval_error": rec.get("eval_error"), "eval_ms": rec.get("eval_ms")}

    # --------------------------------------------------------- internals --
    def _make_record(self, result: dict) -> dict:
        retrieval = result.get("retrieval") or {}
        subs = retrieval.get("sub_queries", [])
        return {
            "query_id": result["query_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "question": result["question"],
            "standalone_question": result["plan"]["standalone_question"],
            "route": result["plan"]["route"],
            "planner": result["plan"]["planner"],
            "sub_questions": result["plan"]["sub_questions"],
            "mode": result["mode"],
            "answer": result["answer"],
            "contexts": [{"id": s["id"], "chunk_id": s["chunk_id"], "source": s["source"], "page": s["page"],
                          "section": s["section"], "cited": s["cited"], "text": s["text"]}
                         for s in result["sources"]],
            "retrieval": {
                "reranked": retrieval.get("reranked"),
                "per_sub_question": [{
                    "question": sq["question"],
                    "faiss_order": [c["chunk_id"] for c in sorted(sq["candidates"], key=lambda c: c["faiss_rank"])],
                    "final_order": [c["chunk_id"] for c in sq["candidates"]],
                    "selected": [c["chunk_id"] for c in sq["candidates"] if c["selected"]],
                } for sq in subs],
            },
            "scores": {k: None for k in LIVE_METRICS},
            "eval_status": "queued",
            "eval_error": None,
            "eval_ms": None,
            "timings": result.get("timings"),
            "models": {**(result.get("models") or {}), "judge": self.settings.judge_model_name},
        }

    def _remember(self, rec: dict) -> None:
        self.records[rec["query_id"]] = rec
        if rec["query_id"] not in self.order:
            self.order.append(rec["query_id"])
        while len(self.records) > 1000:  # bound memory
            oldest = self.order.popleft() if self.order else None
            self.records.pop(oldest, None)

    @staticmethod
    def to_log_line(rec: dict) -> dict:
        """The JSONL shape: the reference project's keys first (timestamp,
        question, answer_preview, metrics), then this project's extra detail."""
        scores = rec.get("scores") or {}
        head = {
            "timestamp": rec["timestamp"],
            "query_id": rec["query_id"],
            "question": rec["question"],
            "answer_preview": (rec.get("answer") or "")[:200],
            "metrics": {**{k: scores.get(k) for k in LIVE_METRICS},
                        "context_recall": None},  # needs a reference answer: golden set only
        }
        return {**head, **{k: v for k, v in rec.items() if k not in head and k != "scores"}}

    def _append(self, rec: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_log_line(rec), ensure_ascii=False) + "\n")

    async def _run(self) -> None:
        from .chain import strip_citations

        while True:
            query_id = await self.queue.get()
            rec = self.records.get(query_id)
            if rec is None:
                continue
            rec["eval_status"] = "running"
            t0 = time.perf_counter()
            try:
                scores, errors = await self.scorer.score(
                    question=rec["standalone_question"] or rec["question"],
                    answer=strip_citations(rec["answer"]),
                    contexts=[c["text"] for c in rec["contexts"]],
                    metric_names=LIVE_METRICS,
                    before_each=self.llm_provider.chat_idle.wait,  # let live chats go first
                )
                rec["scores"] = scores
                ok = sum(v is not None for v in scores.values())
                rec["eval_status"] = "complete" if ok == len(scores) else ("partial" if ok else "failed")
                rec["eval_error"] = errors or None
            except Exception as e:
                log.exception("Evaluation crashed for %s", query_id)
                rec["eval_status"] = "failed"
                rec["eval_error"] = f"{type(e).__name__}: {e}"
            rec["eval_ms"] = int((time.perf_counter() - t0) * 1000)
            self._append(rec)
