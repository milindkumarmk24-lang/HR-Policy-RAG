"""Builds and holds the long-lived objects (models, index, pipeline, evaluator).

Models are loaded once at startup. Tests replace the embedding and re-ranking
models with lightweight stand-ins through `build_state(embeddings=..., scorer=...)`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from langchain_core.embeddings import Embeddings

from .chain import RAGPipeline
from .config import Settings
from .evaluation import EvalService
from .llm import LLMProvider
from .reranker import CrossEncoderScorer, Scorer
from .retrieval import Retriever
from .vectorstore import IndexManager, make_embeddings

log = logging.getLogger(__name__)


@dataclass
class AppState:
    settings: Settings
    embeddings: Embeddings
    scorer: Scorer | None
    index: IndexManager
    llm: LLMProvider
    retriever: Retriever
    pipeline: RAGPipeline
    evals: EvalService

    def rebuild_pipeline(self) -> None:
        self.pipeline = RAGPipeline(self.settings, self.llm, self.retriever)


def build_state(settings: Settings, embeddings: Embeddings | None = None, scorer: Scorer | None = None,
                load_reranker: bool = True) -> AppState:
    settings.ensure_dirs()
    if embeddings is None:
        log.info("Loading embedding model %s", settings.embedding_model)
        embeddings = make_embeddings(settings.embedding_model)
    if scorer is None and load_reranker:
        log.info("Loading cross-encoder %s", settings.reranker_model)
        scorer = CrossEncoderScorer(settings.reranker_model)

    index = IndexManager(embeddings, settings.index_dir, settings.uploads_dir, settings.embedding_model,
                         settings.chunk_size, settings.chunk_overlap)
    index.load()
    if index.is_empty and settings.autoload_sample:
        for pdf in settings.sample_pdfs:
            try:
                index.add_pdf(pdf, pdf.name, is_sample=True)
            except Exception:  # one unreadable sample shouldn't stop the app
                log.exception("Could not index sample %s", pdf.name)

    llm = LLMProvider(settings)
    if not llm.available:
        log.warning("GOOGLE_API_KEY not set: running in retrieval-only mode (no answers, no RAGAS).")
    retriever = Retriever(index, scorer, settings.fetch_k, settings.top_n, settings.top_n_per_subquestion,
                          settings.max_context_chunks, settings.min_relevance,
                          settings.summary_fetch_k, settings.summary_chunks)
    pipeline = RAGPipeline(settings, llm, retriever)
    evals = EvalService(settings, llm, embeddings)
    return AppState(settings, embeddings, scorer, index, llm, retriever, pipeline, evals)
