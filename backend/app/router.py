"""Query routing and decomposition.

One structured-output LLM call turns the raw user message into a QueryPlan:
which route to take, a standalone rewrite (so follow-ups like "what about
interns?" retrieve the right section), and, for multi-part questions, a list
of sub-questions that are retrieved and re-ranked separately.

If the LLM call fails (no key, quota exhausted, malformed output) a simple
rule-based planner takes over, so the app degrades instead of erroring.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field, field_validator

from .ingest import CATEGORY_NAMES
from .prompts import ROUTER_PROMPT

log = logging.getLogger(__name__)

Route = Literal["policy_lookup", "multi_part", "summary", "chitchat", "out_of_scope"]


class RouterOutput(BaseModel):
    """The schema the LLM fills in (sent to Gemini as a JSON schema)."""

    route: Route = Field(description="How to handle the message.")
    standalone_question: str = Field(description="The latest message rewritten as a self-contained question.")
    sub_questions: list[str] = Field(default_factory=list,
                                     description="1 item for policy_lookup and summary, 2-4 for multi_part, "
                                                 "empty otherwise.")
    topic: str = Field(default="General",
                       description="Main policy area. One of: " + ", ".join(CATEGORY_NAMES) + ".")
    direct_reply: str | None = Field(default=None,
                                     description="Short reply, only for chitchat or out_of_scope; otherwise null.")

    @field_validator("sub_questions")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        out, seen = [], set()
        for q in v:
            q = q.strip()
            if q and q.lower() not in seen:
                seen.add(q.lower())
                out.append(q)
        return out[:4]

    @field_validator("topic")
    @classmethod
    def _topic(cls, v: str) -> str:
        lookup = {c.lower(): c for c in CATEGORY_NAMES}
        return lookup.get((v or "").strip().lower(), "General")


class QueryPlan(RouterOutput):
    planner: Literal["llm", "rules"] = "llm"

    @property
    def needs_retrieval(self) -> bool:
        return self.route in ("policy_lookup", "multi_part", "summary")


def normalise_plan(plan: QueryPlan, question: str) -> QueryPlan:
    """Make the plan internally consistent whatever the model returned."""
    standalone = plan.standalone_question.strip() or question.strip()
    subs = plan.sub_questions
    route = plan.route
    if route == "multi_part" and len(subs) < 2:
        route = "policy_lookup"
    if route in ("policy_lookup", "summary"):
        subs = subs[:1] or [standalone]
    if route in ("chitchat", "out_of_scope"):
        subs = []
    reply = plan.direct_reply if route in ("chitchat", "out_of_scope") else None
    if route in ("chitchat", "out_of_scope") and not reply:
        reply = ("Hi! Ask me about the policies in your handbook, such as leave, benefits or conduct."
                 if route == "chitchat" else
                 "I can only help with questions about the HR policies in your uploaded handbook.")
    return plan.model_copy(update={"route": route, "standalone_question": standalone,
                                   "sub_questions": subs, "direct_reply": reply})


# --------------------------------------------------------------------------- #
# Rule-based fallback planner
# --------------------------------------------------------------------------- #
GREETING = re.compile(r"^\s*(hi|hello|hey|hiya|namaste|good (morning|afternoon|evening)|thanks?|thank you|"
                      r"ok(ay)?|cool|great)\b[\s!.?]*$", re.IGNORECASE)
SUMMARY = re.compile(r"\b(summar(y|ise|ize|ies)|overview|outline|key points|tl;?dr|in a nutshell|walk me through)\b",
                     re.IGNORECASE)
SPLIT = re.compile(
    r"\?\s+(?=\S)|;\s+|\s+(?:and also|also,|and what about|and how about|plus)\s+"
    r"|,?\s+and\s+(?=(?:what|how|when|where|who|which|whom|can|could|is|are|do|does|will|should|must)\b)",
    re.IGNORECASE,
)


def rule_based_plan(question: str) -> QueryPlan:
    q = question.strip()
    if GREETING.match(q):
        return normalise_plan(QueryPlan(route="chitchat", standalone_question=q, planner="rules"), q)
    if SUMMARY.search(q):
        return QueryPlan(route="summary", standalone_question=q, sub_questions=[q], planner="rules")
    parts = [p.strip(" ?.,") for p in SPLIT.split(q)]
    parts = [p + "?" for p in parts if len(p.split()) >= 3]
    if len(parts) >= 2:
        return QueryPlan(route="multi_part", standalone_question=q, sub_questions=parts[:4], planner="rules")
    return QueryPlan(route="policy_lookup", standalone_question=q, sub_questions=[q], planner="rules")


def format_history(history: list[dict], max_turns: int = 6, max_chars: int = 600) -> str:
    if not history:
        return "(none)"
    lines = []
    for turn in history[-max_turns:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        text = re.sub(r"\s*\[S\d+\]", "", str(turn.get("content", ""))).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def build_router(llm) -> Runnable:
    """LCEL: prompt | structured LLM, with the rule-based planner as fallback.

    Input: {"question": str, "history": list[dict]}. Output: QueryPlan.
    """
    fallback = RunnableLambda(lambda x: rule_based_plan(x["question"]))
    if llm is None:
        return fallback

    structured = llm.with_structured_output(RouterOutput)
    chain = (
        RunnableLambda(lambda x: {"question": x["question"], "history": format_history(x.get("history") or [])})
        | ROUTER_PROMPT
        | structured
    )

    def _validate(out, question: str) -> QueryPlan:
        data = out.model_dump() if isinstance(out, BaseModel) else dict(out)
        return normalise_plan(QueryPlan(**data, planner="llm"), question)

    with_check = (
        {"plan": chain, "question": RunnableLambda(lambda x: x["question"])}
        | RunnableLambda(lambda x: _validate(x["plan"], x["question"]))
    )
    return with_check.with_fallbacks([fallback])
