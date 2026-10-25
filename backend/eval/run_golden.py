"""Run the full pipeline over the golden set and score it with RAGAS,
including the reference-based metrics that live queries can't have.

Needs GOOGLE_API_KEY. At ~12 judge calls per question and 14 requests/minute,
25 questions take roughly 25-30 minutes on a free-tier key; use --limit to try
a few first.

    python eval/run_golden.py --limit 5
    python eval/run_golden.py                       # full set, with re-ranking
    python eval/run_golden.py --no-rerank           # same, FAISS order only (for comparison)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from datetime import datetime, timezone

from common import RESULTS, eval_state, load_golden, update_readme

from app.chain import ChatOptions, strip_citations
from app.evaluation import RagasScorer
from app.prompts import NOT_FOUND_TEXT

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_precision_ref", "context_recall")


async def run(args) -> None:
    state = eval_state()
    if not state.llm.available:
        raise SystemExit("GOOGLE_API_KEY is not set. Add it to backend/.env first.")
    scorer = RagasScorer(state.settings, state.llm, state.embeddings, with_reference=True)
    items = load_golden()[: args.limit] if args.limit else load_golden()
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    variant = "norerank" if args.no_rerank else "rerank"
    out_path = RESULTS / f"golden_{stamp}_{variant}.jsonl"

    records = []
    for i, item in enumerate(items, 1):
        t0 = time.perf_counter()
        result = await state.pipeline.run(item["question"], options=ChatOptions(rerank=not args.no_rerank))
        contexts = [s["text"] for s in result["sources"]]
        gold = set(item["gold_sections"])
        retrieved = {s["section"] for s in result["sources"]}
        cited_pages = {p for s in result["sources"] if s["cited"] for p in range(s["page"], s["page_end"] + 1)}
        rec = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "id": item["id"], "type": item["type"], "question": item["question"],
            "answer_preview": result["answer"][:200], "answer": result["answer"],
            "route": result["plan"]["route"], "sub_questions": result["plan"]["sub_questions"],
            "gold_sections": item["gold_sections"], "gold_pages": item["gold_pages"],
            "retrieved_sections": sorted(s for s in retrieved if s),
            "section_recall": (len(gold & retrieved) / len(gold)) if gold else None,
            "citation_page_hit": (bool(cited_pages & set(item["gold_pages"])) if item["gold_pages"] else None),
        }
        if item["type"] == "unanswerable":
            rec["correct_refusal"] = NOT_FOUND_TEXT.lower()[:25] in result["answer"].lower()
            rec["scores"] = {}
        else:
            scores, errors = await scorer.score(item["question"], strip_citations(result["answer"]), contexts,
                                                reference=item["reference"], metric_names=METRICS)
            rec["scores"], rec["errors"] = scores, errors or None
        # Same "metrics" block as the live log (reference-project format).
        rec["metrics"] = {k: rec["scores"].get(k) for k in
                          ("faithfulness", "answer_relevancy", "context_precision", "context_recall")}
        rec["seconds"] = round(time.perf_counter() - t0, 1)
        records.append(rec)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(items)}] {item['id']} route={rec['route']} "
              + " ".join(f"{k}={v:.2f}" for k, v in rec["scores"].items() if v is not None)
              + (f" refusal_ok={rec['correct_refusal']}" if "correct_refusal" in rec else ""))

    answerable = [r for r in records if r["type"] != "unanswerable"]
    lines = [f"Golden set: {len(records)} questions ({len(answerable)} answerable), variant: **{variant}**, "
             f"generator `{state.settings.gemini_model}`, judge `{state.settings.judge_model_name}`, "
             f"run {datetime.now().strftime('%Y-%m-%d')}.", "", "| Metric | Mean | n |", "|---|---|---|"]
    for m in METRICS:
        vals = [r["scores"][m] for r in answerable if r["scores"].get(m) is not None]
        if vals:
            lines.append(f"| RAGAS {m} | {statistics.mean(vals):.3f} | {len(vals)} |")
    sec = [r["section_recall"] for r in answerable if r["section_recall"] is not None]
    cit = [r["citation_page_hit"] for r in answerable if r["citation_page_hit"] is not None]
    ref = [r["correct_refusal"] for r in records if "correct_refusal" in r]
    if sec:
        lines.append(f"| Gold-section recall in context | {statistics.mean(sec):.3f} | {len(sec)} |")
    if cit:
        lines.append(f"| Answer cites a gold page | {statistics.mean(cit):.3f} | {len(cit)} |")
    if ref:
        lines.append(f"| Correct refusal on unanswerable questions | {statistics.mean(ref):.3f} | {len(ref)} |")
    table = "\n".join(lines)
    summary_path = out_path.with_suffix(".md")
    summary_path.write_text(table + "\n", encoding="utf-8")
    print("\n" + table + f"\n\nWrote {out_path} and {summary_path}")
    if not args.limit and not args.no_rerank and update_readme("golden", table):
        print("Updated README.md")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="only the first N questions")
    ap.add_argument("--no-rerank", action="store_true", help="skip the cross-encoder (FAISS order)")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
