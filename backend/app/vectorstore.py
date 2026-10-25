"""Local embeddings + a persistent FAISS index, plus a small registry of the
documents that are in it.

Embeddings are computed on this machine with sentence-transformers (no API
calls, no cost). Vectors are L2-normalised and stored in an inner-product
FAISS index, so the score FAISS returns is cosine similarity (higher = closer).
"""
from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from .ingest import chunk_body, chunk_pdf, file_sha

log = logging.getLogger(__name__)


def make_embeddings(model_name: str) -> Embeddings:
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
    )


def print_chunks(chunks: list[Document], filename: str) -> None:
    """Console summary of a freshly chunked PDF: one line per chunk."""
    log.info("Chunked %s into %d chunks:", filename, len(chunks))
    for c in chunks:
        m = c.metadata
        pages = f"p.{m['page']}" + (f"-{m['page_end']}" if m["page_end"] != m["page"] else "")
        log.info("  %-18s %-8s %-44s %4d chars", m["chunk_id"], pages, (m.get("section") or "-")[:44],
                 len(chunk_body(c)))


@dataclass
class DocRecord:
    doc_id: str
    filename: str
    pages: int
    chunks: int
    chunk_ids: list[str]
    added_at: float = field(default_factory=time.time)
    is_sample: bool = False

    def public(self) -> dict:
        d = asdict(self)
        d.pop("chunk_ids")
        return d


class IndexManager:
    """Owns the FAISS store, the uploaded PDFs and the document registry."""

    def __init__(self, embeddings: Embeddings, index_dir: Path, uploads_dir: Path, embedding_model: str,
                 chunk_size: int = 1000, chunk_overlap: int = 150):
        self.embeddings = embeddings
        self.index_dir = index_dir
        self.uploads_dir = uploads_dir
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.store: FAISS | None = None
        self.docs: dict[str, DocRecord] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ io --
    @property
    def _registry_path(self) -> Path:
        return self.index_dir / "documents.json"

    def load(self) -> None:
        """Load a previously saved index. Rebuilds it if the embedding model changed."""
        with self._lock:
            if not self._registry_path.exists():
                return
            meta = json.loads(self._registry_path.read_text(encoding="utf-8"))
            records = [DocRecord(**d) for d in meta.get("documents", [])]
            if meta.get("embedding_model") != self.embedding_model:
                log.warning("Embedding model changed (%s -> %s); re-indexing %d document(s)",
                            meta.get("embedding_model"), self.embedding_model, len(records))
                self._wipe_index_files()
                for r in records:
                    pdf = self.pdf_path(r.doc_id)
                    if pdf.exists():
                        self.add_pdf(pdf, r.filename, is_sample=r.is_sample, _copy=False)
                return
            if (self.index_dir / "index.faiss").exists() and records:
                # The pickle file is one we wrote ourselves. Never load index files
                # from an untrusted source with allow_dangerous_deserialization.
                self.store = FAISS.load_local(str(self.index_dir), self.embeddings,
                                              allow_dangerous_deserialization=True)
                self.docs = {r.doc_id: r for r in records}
                log.info("Loaded FAISS index: %d document(s), %d vectors", len(self.docs), self.vector_count)

    def _save(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        if self.store is not None:
            self.store.save_local(str(self.index_dir))
        payload = {"embedding_model": self.embedding_model,
                   "documents": [asdict(r) for r in self.docs.values()]}
        self._registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _wipe_index_files(self) -> None:
        for name in ("index.faiss", "index.pkl", "documents.json"):
            (self.index_dir / name).unlink(missing_ok=True)
        self.store = None
        self.docs = {}

    # ------------------------------------------------------------- queries --
    @property
    def vector_count(self) -> int:
        return int(self.store.index.ntotal) if self.store is not None else 0

    @property
    def is_empty(self) -> bool:
        return self.store is None or self.vector_count == 0

    def pdf_path(self, doc_id: str) -> Path:
        return self.uploads_dir / f"{doc_id}.pdf"

    def list_documents(self) -> list[dict]:
        return [r.public() for r in sorted(self.docs.values(), key=lambda r: r.added_at)]

    def search(self, query: str, k: int) -> list[tuple[Document, float]]:
        if self.is_empty:
            return []
        with self._lock:
            return self.store.similarity_search_with_score(query, k=min(k, self.vector_count))

    def query_index(self, question: str, k: int = 5) -> list[dict]:
        """Top-k chunks for a question, with cosine similarity, as plain dicts."""
        out = []
        for rank, (d, score) in enumerate(self.search(question, k), start=1):
            m = d.metadata
            out.append({"rank": rank, "score": round(float(score), 4), "chunk_id": m["chunk_id"],
                        "source": m["source"], "page": m["page"], "section": m.get("section"),
                        "snippet": chunk_body(d)[:160].replace("\n", " ")})
        return out

    def chunks_for(self, doc_id: str) -> list[Document]:
        if self.store is None or doc_id not in self.docs:
            return []
        ids = self.docs[doc_id].chunk_ids
        return [d for d in (self.store.docstore.search(i) for i in ids) if isinstance(d, Document)]

    # ------------------------------------------------------------- updates --
    def add_pdf(self, src: Path, filename: str, is_sample: bool = False, _copy: bool = True) -> DocRecord:
        doc_id = file_sha(src)[:12]
        with self._lock:
            if doc_id in self.docs:
                return self.docs[doc_id]
            self.uploads_dir.mkdir(parents=True, exist_ok=True)
            dest = self.pdf_path(doc_id)
            if _copy and src.resolve() != dest.resolve():
                shutil.copyfile(src, dest)
            chunks, pages = chunk_pdf(dest, doc_id, filename, self.chunk_size, self.chunk_overlap)
            if not chunks:
                dest.unlink(missing_ok=True)
                raise ValueError("No extractable text found. Scanned (image-only) PDFs need OCR first.")
            print_chunks(chunks, filename)
            ids = [c.metadata["chunk_id"] for c in chunks]
            if self.store is None:
                self.store = FAISS.from_documents(chunks, self.embeddings, ids=ids,
                                                  distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT)
            else:
                self.store.add_documents(chunks, ids=ids)
            record = DocRecord(doc_id=doc_id, filename=filename, pages=pages, chunks=len(chunks),
                               chunk_ids=ids, is_sample=is_sample)
            self.docs[doc_id] = record
            self._save()
            log.info("Indexed %s: %d pages -> %d chunks", filename, pages, len(chunks))
            return record

    def remove(self, doc_id: str) -> bool:
        with self._lock:
            record = self.docs.pop(doc_id, None)
            if record is None:
                return False
            if self.store is not None:
                self.store.delete(ids=record.chunk_ids)
                if self.vector_count == 0:
                    self.store = None
            self.pdf_path(doc_id).unlink(missing_ok=True)
            if self.store is None:
                self._wipe_index_files()
            else:
                self._save()
            return True

    def reset(self) -> None:
        with self._lock:
            for doc_id in list(self.docs):
                self.pdf_path(doc_id).unlink(missing_ok=True)
            self._wipe_index_files()
