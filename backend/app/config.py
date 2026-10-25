"""Application settings, read from environment variables or a .env file.

Every knob lives here so the rest of the code never calls os.getenv directly.
See .env.example at the repo root for the full list with explanations.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent

# RAGAS ships anonymous usage analytics; keep evaluation fully local.
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
# Silence the tokenizers fork warning that appears under uvicorn --reload.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # backend/.env wins over a repo-root .env; both are optional.
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- LLM (Google Gemini) -------------------------------------------------
    google_api_key: str | None = Field(default=None, description="Gemini API key from Google AI Studio")
    gemini_model: str = "gemini-3.5-flash-lite"
    judge_model: str | None = Field(default=None, description="Model RAGAS uses as judge; defaults to gemini_model")
    llm_temperature: float = 0.1
    # Free-tier keys allow roughly 15 requests/minute per model. One shared limiter
    # keeps answers + RAGAS judge calls under that ceiling.
    gemini_rpm: int = 14
    llm_max_retries: int = 4
    llm_timeout_s: float = 60.0

    # ---- Retrieval -----------------------------------------------------------
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    chunk_size: int = 1000          # characters (~250 tokens)
    chunk_overlap: int = 150
    fetch_k: int = 12               # FAISS candidates per (sub-)question, before re-ranking
    top_n: int = 4                  # chunks kept per single question after re-ranking
    top_n_per_subquestion: int = 3  # chunks kept per sub-question for multi-part questions
    max_context_chunks: int = 8     # hard cap on chunks sent to the LLM
    min_relevance: float = 0.01     # drop re-ranked chunks below this probability (always keeps the best one)
    summary_fetch_k: int = 24       # wider candidate pool for "summarise X" requests
    summary_chunks: int = 10        # chunks kept for a summary, put back in handbook order

    # ---- Evaluation ----------------------------------------------------------
    eval_enabled: bool = True
    answer_relevancy_strictness: int = 3

    # ---- App -----------------------------------------------------------------
    data_dir: Path = BACKEND_DIR / "data"          # runtime state: index, uploads, logs
    sample_dir: Path = BACKEND_DIR / "data" / "sample"  # bundled handbooks, indexed on first start
    autoload_sample: bool = True
    max_upload_mb: int = 25
    max_documents: int = 8
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Any Vercel deployment (production and preview URLs) may call the API.
    cors_origin_regex: str = r"https://[a-z0-9-]+\.vercel\.app"
    frontend_dist: Path = REPO_DIR / "frontend" / "out"

    # ---- Derived paths ---------------------------------------------------------
    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def eval_log_path(self) -> Path:
        return self.logs_dir / "ragas_eval.jsonl"

    @property
    def sample_pdfs(self) -> list[Path]:
        return sorted(self.sample_dir.glob("*.pdf")) if self.sample_dir.exists() else []

    @property
    def judge_model_name(self) -> str:
        return self.judge_model or self.gemini_model

    @property
    def has_api_key(self) -> bool:
        return bool(self.google_api_key and self.google_api_key.strip()
                    and not self.google_api_key.startswith("your-"))

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        for d in (self.index_dir, self.uploads_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
