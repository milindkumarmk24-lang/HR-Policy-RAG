"""Request bodies for the HTTP API (responses are plain dicts, documented in the README)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=6000)


class ChatOptionsIn(BaseModel):
    rerank: bool = Field(default=True, description="Re-rank FAISS candidates with the cross-encoder")
    top_n: int | None = Field(default=None, ge=1, le=10, description="Chunks to keep for a single question")
    evaluate: bool = Field(default=True, description="Queue RAGAS evaluation for this answer")
    retrieval_only: bool = Field(default=False, description="Skip generation; return retrieved passages only")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=20)
    options: ChatOptionsIn = Field(default_factory=ChatOptionsIn)
