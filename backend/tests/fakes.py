"""Offline stand-ins so the whole pipeline (routing, FAISS, re-ranking, LCEL,
streaming, RAGAS plumbing) can be tested without model downloads or an API key.

- HashingEmbeddings: bag-of-words hashed into a fixed-size, L2-normalised vector.
- LexicalScorer: word-overlap "cross-encoder".
- FakeGemini: a LangChain chat model that answers the router, the answer
  prompt and RAGAS judge prompts (by filling in the JSON schema RAGAS sends).
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from typing import Any, Iterator

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import RunnableLambda

STOP = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "for", "in", "on", "do", "i", "my", "how",
        "what", "can", "be", "it", "at", "by", "with", "you", "your", "does", "many", "much", "any", "if"}


def words(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.append(w)
    return out


class HashingEmbeddings(Embeddings):
    def __init__(self, dim: int = 1024):
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for w in words(text):
            h = int(hashlib.md5(w.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 20) % 2 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class LexicalScorer:
    model_name = "lexical-test-scorer"

    def score(self, query: str, passages) -> list[float]:
        q = set(words(query))
        out = []
        for p in passages:
            pw = words(p)
            overlap = sum(1 for w in set(pw) if w in q)
            out.append(overlap * 2.0 - 4.0)
        return out


def _instance(schema: dict, defs: dict, rng: random.Random) -> Any:
    if "$ref" in schema:
        return _instance(defs[schema["$ref"].split("/")[-1]], defs, rng)
    if "anyOf" in schema:
        options = [s for s in schema["anyOf"] if s.get("type") != "null"]
        return _instance(options[0], defs, rng)
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object":
        return {k: _instance(v, defs, rng) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return [_instance(schema.get("items", {}), defs, rng) for _ in range(2)]
    if t == "integer":
        return rng.choice([0, 1, 1, 1])  # mostly "supported/useful", sometimes not
    if t == "number":
        return 0.5
    if t == "boolean":
        return True
    return "How many days of sick leave do employees receive?"


class FakeGemini(BaseChatModel):
    temperature: float = 0.0
    n: int = 1
    seed: int = 7

    @property
    def _llm_type(self) -> str:
        return "fake-gemini"

    def _reply(self, messages: list[BaseMessage]) -> str:
        text = "\n".join(str(m.content) for m in messages)
        m = re.search(r"JSON Schema:\n(\{.*?\})Do not use single quotes", text, re.DOTALL)
        if m:  # a RAGAS judge prompt
            schema = json.loads(m.group(1))
            rng = random.Random(self.seed + len(text))
            return json.dumps(_instance(schema, schema.get("$defs", {}), rng))
        if "<source id=" in text:  # the answer prompt
            ids = re.findall(r'<source id="(S\d+)"', text)
            body = re.search(r'<source id="S1"[^>]*>\n(.*?)\n</source>', text, re.DOTALL)
            first = body.group(1).split("\n")[1:2] if body else [""]
            return f"According to the handbook, {first[0].strip()[:160]} [{ids[0]}]. See also [S9]."
        return "OK"

    def _generate(self, messages, stop=None, run_manager: CallbackManagerForLLMRun | None = None, **kw):
        msg = AIMessage(content=self._reply(messages), response_metadata={"finish_reason": "STOP"})
        return ChatResult(generations=[ChatGeneration(message=msg, generation_info={"finish_reason": "STOP"})])

    def _stream(self, messages, stop=None, run_manager=None, **kw) -> Iterator[ChatGenerationChunk]:
        for piece in re.findall(r"\S+\s*", self._reply(messages)):
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece))

    def with_structured_output(self, schema, **kwargs):
        from app.router import rule_based_plan

        def plan(prompt_value) -> Any:
            text = prompt_value.to_string()
            latest = text.rsplit("Latest user message:\n", 1)[-1].strip()
            p = rule_based_plan(latest)
            data = p.model_dump(exclude={"planner"})
            if p.route == "chitchat":
                data["direct_reply"] = "Hello from the fake model!"
            return schema(**data)

        return RunnableLambda(plan)
