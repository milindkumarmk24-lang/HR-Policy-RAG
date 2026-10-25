"""Two-stage retrieval: FAISS (fast, recall-oriented) -> cross-encoder
re-ranking (slow, precision-oriented), run once per sub-question.

Every candidate keeps both its FAISS rank and its re-ranked rank, so the UI and
the README can show exactly how re-ranking changed the order.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.documents import Document

from .ingest import chunk_body
from .reranker import Scorer, sigmoid
from .vectorstore import IndexManager


@dataclass
class Candidate:
    chunk_id: str
    doc: Document
    faiss_rank: int                  # 1-based rank from vector search
    faiss_score: float               # cosine similarity
    rerank_score: float | None = None  # cross-encoder logit
    relevance: float | None = None     # sigmoid(rerank_score), 0..1
    rerank_rank: int | None = None
    selected: bool = False

    def summary(self) -> dict:
        m = self.doc.metadata
        return {
            "chunk_id": self.chunk_id,
            "doc_id": m.get("doc_id"),
            "source": m.get("source"),
            "page": m.get("page"),
            "section": m.get("section"),
            "preview": chunk_body(self.doc)[:220],
            "faiss_rank": self.faiss_rank,
            "faiss_score": round(self.faiss_score, 4),
            "rerank_rank": self.rerank_rank,
            "rerank_score": None if self.rerank_score is None else round(self.rerank_score, 3),
            "relevance": None if self.relevance is None else round(self.relevance, 4),
            "selected": self.selected,
        }


@dataclass
class SubQueryResult:
    question: str
    candidates: list[Candidate]      # in final order (re-ranked if enabled)


@dataclass
class RetrievalResult:
    sub_results: list[SubQueryResult] = field(default_factory=list)
    context: list[Candidate] = field(default_factory=list)  # what the LLM sees, in order
    reranked: bool = True
    fetch_k: int = 0

    def summary(self) -> dict:
        return {
            "reranked": self.reranked,
            "fetch_k": self.fetch_k,
            "sub_queries": [{"question": s.question, "candidates": [c.summary() for c in s.candidates]}
                            for s in self.sub_results],
        }


class Retriever:
    def __init__(self, index: IndexManager, scorer: Scorer | None, fetch_k: int = 12, top_n: int = 4,
                 top_n_per_subquestion: int = 3, max_context_chunks: int = 8, min_relevance: float = 0.01,
                 summary_fetch_k: int = 24, summary_chunks: int = 10):
        self.index = index
        self.scorer = scorer
        self.fetch_k = fetch_k
        self.top_n = top_n
        self.top_n_per_sub = top_n_per_subquestion
        self.max_context = max_context_chunks
        self.min_relevance = min_relevance
        self.summary_fetch_k = summary_fetch_k
        self.summary_chunks = summary_chunks

    def retrieve_one(self, question: str, keep: int, rerank: bool = True,
                     fetch_k: int | None = None) -> SubQueryResult:
        hits = self.index.search(question, fetch_k or self.fetch_k)
        cands = [Candidate(chunk_id=d.metadata["chunk_id"], doc=d, faiss_rank=i + 1, faiss_score=float(s))
                 for i, (d, s) in enumerate(hits)]
        if rerank and self.scorer is not None and cands:
            scores = self.scorer.score(question, [c.doc.page_content for c in cands])
            for c, s in zip(cands, scores):
                c.rerank_score = s
                c.relevance = sigmoid(s)
            cands.sort(key=lambda c: c.rerank_score, reverse=True)
            for i, c in enumerate(cands):
                c.rerank_rank = i + 1
            chosen = [c for c in cands[:keep] if c.relevance >= self.min_relevance] or cands[:1]
        else:
            chosen = cands[:keep]
        for c in chosen:
            c.selected = True
        return SubQueryResult(question=question, candidates=cands)

    def retrieve(self, sub_questions: list[str], rerank: bool = True, top_n: int | None = None) -> RetrievalResult:
        multi = len(sub_questions) > 1
        keep = self.top_n_per_sub if multi else (top_n or self.top_n)
        result = RetrievalResult(reranked=rerank and self.scorer is not None, fetch_k=self.fetch_k)
        for q in sub_questions:
            result.sub_results.append(self.retrieve_one(q, keep, rerank))

        # Interleave the sub-questions' picks (best of each first), de-duplicated,
        # so every part of a multi-part question is represented in the context.
        picks = [[c for c in s.candidates if c.selected] for s in result.sub_results]
        seen: set[str] = set()
        for rank in range(max((len(p) for p in picks), default=0)):
            for p in picks:
                if rank < len(p) and p[rank].chunk_id not in seen:
                    seen.add(p[rank].chunk_id)
                    result.context.append(p[rank])
        result.context = result.context[: self.max_context]
        return result


    def retrieve_summary(self, query: str, rerank: bool = True) -> RetrievalResult:
        """For "summarise X": a wider candidate pool, more chunks kept, and the
        context put back into handbook order so the summary follows the
        document's own structure rather than relevance order."""
        result = RetrievalResult(reranked=rerank and self.scorer is not None, fetch_k=self.summary_fetch_k)
        sub = self.retrieve_one(query, self.summary_chunks, rerank, fetch_k=self.summary_fetch_k)
        result.sub_results.append(sub)
        order = {d: i for i, d in enumerate(self.index.docs)}
        chosen = [c for c in sub.candidates if c.selected]
        result.context = sorted(chosen, key=lambda c: (order.get(c.doc.metadata.get("doc_id"), 0),
                                                       c.doc.metadata.get("chunk_index", 0)))
        return result


def format_context(context: list[Candidate]) -> str:
    blocks = []
    for i, c in enumerate(context, start=1):
        m = c.doc.metadata
        page = m.get("page")
        if m.get("page_end") and m.get("page_end") != page:
            page = f"{page}-{m['page_end']}"
        attrs = f'id="S{i}" document="{m.get("source")}" page="{page}"'
        if m.get("section"):
            attrs += f' section="{m["section"]}"'
        blocks.append(f"<source {attrs}>\n{chunk_body(c.doc)}\n</source>")
    return "\n\n".join(blocks)


def candidate_to_source(c: Candidate, idx: int) -> dict:
    m = c.doc.metadata
    d = c.summary()
    d.pop("preview")
    d.update({
        "id": f"S{idx}",
        "page_end": m.get("page_end"),
        "chapter": m.get("chapter"),
        "category": m.get("category"),
        "text": chunk_body(c.doc),
    })
    return d


__all__ = ["Candidate", "RetrievalResult", "Retriever", "format_context", "candidate_to_source"]
