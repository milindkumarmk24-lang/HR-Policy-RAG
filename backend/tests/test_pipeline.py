import asyncio

import pytest

from app.chain import ChatOptions
from app.router import normalise_plan, QueryPlan, rule_based_plan


def test_rule_based_router():
    assert rule_based_plan("hello!").route == "chitchat"
    p = rule_based_plan("How many sick days do I get? What is the notice period for managers?")
    assert p.route == "multi_part" and len(p.sub_questions) == 2
    p = rule_based_plan("Can I carry forward casual leave, and what is the notice period at L3?")
    assert p.route == "multi_part" and p.sub_questions[1].startswith("what is the notice period")
    p = rule_based_plan("Can I work from home on Tuesdays and Thursdays?")
    assert p.route == "policy_lookup" and p.sub_questions == ["Can I work from home on Tuesdays and Thursdays?"]


def test_normalise_plan_fixes_inconsistent_output():
    p = normalise_plan(QueryPlan(route="multi_part", standalone_question="q", sub_questions=["only one"]), "q")
    assert p.route == "policy_lookup" and p.sub_questions == ["only one"]
    p = normalise_plan(QueryPlan(route="out_of_scope", standalone_question="q", sub_questions=["x"]), "q")
    assert p.sub_questions == [] and p.direct_reply


def test_retrieval_reranks_and_tracks_ranks(make_settings, state_factory):
    state = state_factory(make_settings())
    assert state.index.vector_count > 40
    res = state.retriever.retrieve(["Is a medical certificate required for sick leave?"], rerank=True)
    sub = res.sub_results[0]
    assert len(sub.candidates) == state.settings.fetch_k
    assert [c.rerank_rank for c in sub.candidates] == list(range(1, len(sub.candidates) + 1))
    assert sorted(c.faiss_rank for c in sub.candidates) == list(range(1, len(sub.candidates) + 1))
    assert res.context and res.context[0].doc.metadata["section"] == "3.4 Sick Leave"
    off = state.retriever.retrieve(["Is a medical certificate required for sick leave?"], rerank=False)
    assert [c.faiss_rank for c in off.sub_results[0].candidates] == list(range(1, state.settings.fetch_k + 1))
    assert all(c.rerank_score is None for c in off.sub_results[0].candidates)


def test_multi_part_context_covers_every_sub_question(make_settings, state_factory):
    state = state_factory(make_settings())
    res = state.retriever.retrieve(["How many days of paternity leave?", "What is the hotel limit in Mumbai?"])
    sections = [c.doc.metadata["section"] for c in res.context]
    assert "3.9 Paternity Leave" in sections
    assert "7.2 Hotel Limits and Per Diem" in sections
    assert len(res.context) <= state.settings.max_context_chunks


def test_pipeline_retrieval_only_without_key(make_settings, state_factory):
    state = state_factory(make_settings(api_key=None))
    result = asyncio.run(state.pipeline.run("How many casual leave days do I get?"))
    assert result["mode"] == "retrieval_only"
    assert result["plan"]["planner"] == "rules"
    assert result["sources"] and result["sources"][0]["page"] >= 1


def test_pipeline_with_fake_llm_cites_and_drops_invalid_citations(make_settings, state_factory, fake_llm):
    state = state_factory(make_settings(api_key="test-key"))
    result = asyncio.run(state.pipeline.run("Do I need a medical certificate for sick leave?"))
    assert result["mode"] == "rag"
    assert "[S1]" in result["answer"]
    assert "[S9]" not in result["answer"]  # invented citation removed
    assert result["sources"][0]["cited"] is True
    assert result["retrieval"]["sub_queries"][0]["candidates"]
    assert {"route_ms", "retrieve_ms", "generate_ms", "total_ms"} <= set(result["timings"])


def test_streaming_yields_tokens(make_settings, state_factory, fake_llm):
    state = state_factory(make_settings(api_key="test-key"))

    async def go():
        p = await state.pipeline.prepare("What is the per diem in Bengaluru?", [], ChatOptions())
        return [t async for t in state.pipeline.stream_answer(p)]

    tokens = asyncio.run(go())
    assert len(tokens) > 3


def test_chitchat_skips_retrieval(make_settings, state_factory, fake_llm):
    state = state_factory(make_settings(api_key="test-key"))
    result = asyncio.run(state.pipeline.run("hi"))
    assert result["mode"] == "direct" and result["sources"] == []
    assert result["answer"] == "Hello from the fake model!"


@pytest.mark.parametrize("with_rerank", [True, False])
def test_ragas_scorer_runs_end_to_end(make_settings, state_factory, fake_llm, with_rerank):
    from app.evaluation import LIVE_METRICS, RagasScorer

    state = state_factory(make_settings(api_key="test-key"))
    result = asyncio.run(state.pipeline.run("How many days of bereavement leave?",
                                            options=ChatOptions(rerank=with_rerank)))
    scorer = RagasScorer(state.settings, state.llm, state.embeddings)
    scores, errors = asyncio.run(scorer.score(result["question"], result["answer"],
                                              [s["text"] for s in result["sources"]], metric_names=LIVE_METRICS))
    assert set(scores) == set(LIVE_METRICS)
    for name, value in scores.items():
        assert value is None or 0.0 <= value <= 1.0, (name, value, errors)
    assert any(v is not None for v in scores.values()), errors


def test_query_index_is_deterministic_and_question_specific(make_settings, state_factory):
    """Step 4 checklist: same question twice -> identical top-k; different questions -> different chunks."""
    state = state_factory(make_settings())
    a1 = state.index.query_index("How many days of sick leave do I get?", k=5)
    a2 = state.index.query_index("How many days of sick leave do I get?", k=5)
    b = state.index.query_index("What is the hotel limit for business travel?", k=5)
    assert [r["chunk_id"] for r in a1] == [r["chunk_id"] for r in a2]
    assert [r["score"] for r in a1] == [r["score"] for r in a2]
    assert a1[0]["chunk_id"] != b[0]["chunk_id"]
    assert {"rank", "score", "chunk_id", "source", "page", "section", "snippet"} <= set(a1[0])


def test_summary_route_keeps_more_chunks_in_document_order(make_settings, state_factory, fake_llm):
    state = state_factory(make_settings(api_key="test-key"))
    assert rule_based_plan("Give me an overview of the leave policy").route == "summary"
    result = asyncio.run(state.pipeline.run("Summarise the leave policy"))
    assert result["plan"]["route"] == "summary" and result["mode"] == "rag"
    sources = result["sources"]
    assert 4 <= len(sources) <= state.settings.summary_chunks
    order = [int(s["chunk_id"].split(":")[1]) for s in sources]
    assert order == sorted(order), "summary context should follow handbook order"
    assert result["retrieval"]["fetch_k"] == state.settings.summary_fetch_k
