"""Gemini chat models, created in one place with shared rate limiting.

Free-tier Gemini keys allow roughly 15 requests per minute per model. The
answer generator, the query router and the RAGAS judge all draw from ONE token
bucket, so the app slows down gracefully instead of hitting HTTP 429. The
LangChain wrapper also retries 429/5xx responses with exponential backoff.
"""
from __future__ import annotations

import asyncio
import contextlib

from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter

from .config import Settings


class MissingAPIKey(RuntimeError):
    pass


class LLMProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.limiter = InMemoryRateLimiter(
            requests_per_second=max(settings.gemini_rpm, 1) / 60.0,
            check_every_n_seconds=0.1,
            max_bucket_size=2,
        )
        # Chat requests get priority over background evaluation: the evaluator
        # waits for this event before each metric.
        self._active_chats = 0
        self.chat_idle = asyncio.Event()
        self.chat_idle.set()

    @property
    def available(self) -> bool:
        return self.settings.has_api_key

    def chat_model(self, *, model: str | None = None, temperature: float | None = None,
                   max_output_tokens: int = 2048, max_retries: int | None = None) -> BaseChatModel:
        if not self.available:
            raise MissingAPIKey("GOOGLE_API_KEY is not set. Add it to backend/.env and restart the server.")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model or self.settings.gemini_model,
            google_api_key=self.settings.google_api_key,
            temperature=self.settings.llm_temperature if temperature is None else temperature,
            max_output_tokens=max_output_tokens,
            max_retries=self.settings.llm_max_retries if max_retries is None else max_retries,
            timeout=self.settings.llm_timeout_s,
            rate_limiter=self.limiter,
        )

    @contextlib.asynccontextmanager
    async def chat_priority(self):
        self._active_chats += 1
        self.chat_idle.clear()
        try:
            yield
        finally:
            self._active_chats -= 1
            if self._active_chats <= 0:
                self._active_chats = 0
                self.chat_idle.set()
