"""Download the embedding and re-ranking models ahead of time (used by the
Dockerfile so the container starts without a download).

    python scripts/prefetch_models.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sentence_transformers import CrossEncoder, SentenceTransformer  # noqa: E402

from app.config import get_settings  # noqa: E402

s = get_settings()
print("Fetching", s.embedding_model)
SentenceTransformer(s.embedding_model, device="cpu")
print("Fetching", s.reranker_model)
CrossEncoder(s.reranker_model, device="cpu")
print("Done")
