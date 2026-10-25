"""Before/after comparison: does cross-encoder re-ranking put the right
handbook section higher than FAISS alone?

For every answerable golden question (multi-part ones split into their
sub-questions) we retrieve FAISS's top-k chunks, then re-rank the same
candidates with the cross-encoder, and record where the first chunk from the
gold section lands in each ordering. No API key needed: this is retrieval only.

    python eval/compare_rerank.py            # writes docs/rerank_comparison.md and updates the README
"""
from __future__ import annotations

import argparse
from datetime import date

from common import REPO, eval_state, load_golden, sub_queries, update_readme


def gold_rank(cands, gold: list[str], attr: str) -> int | None:
    ranks = [getattr(c, attr) for c in cands if c.doc.metadata.get("section") in gold]
    return min(ranks) if ranks else None


def metrics(ranks: list[int | None], k: int) -> dict:
    n = len(ranks)
    return {
        "hit@1": sum(1 for r in ranks if r == 1) / n,
        "hit@3": sum(1 for r in ranks if r is not None and r <= 3) / n,
        f"recall@{k}": sum(1 for r in ranks if r is not None) / n,
        "mrr": sum(1 / r for r in ranks if r) / n,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fetch-k", type=int, default=None, help="FAISS candidates per question")
    ap.add_argument("--no-readme", action="store_true", help="don't update README.md")
    args = ap.parse_args()

    state = eval_state(**({"fetch_k": args.fetch_k} if args.fetch_k else {}))
    k = state.settings.fetch_k
    rows = []
    for item in load_golden():
        if item["type"] == "unanswerable":
            continue
        for q, gold in sub_queries(item):
            res = state.retriever.retrieve_one(q, keep=state.settings.top_n, rerank=True)
            before = gold_rank(res.candidates, gold, "faiss_rank")
            after = gold_rank(res.candidates, gold, "rerank_rank")
            faiss_top = min(res.candidates, key=lambda c: c.faiss_rank).doc.metadata.get("section")
            rerank_top = res.candidates[0].doc.metadata.get("section")
            rows.append({"id": item["id"], "question": q, "gold": gold[0], "before": before, "after": after,
                         "faiss_top": faiss_top, "rerank_top": rerank_top})

    mb = metrics([r["before"] for r in rows], k)
    ma = metrics([r["after"] for r in rows], k)
    better = sum(1 for r in rows if r["before"] and r["after"] and r["after"] < r["before"])
    worse = sum(1 for r in rows if r["before"] and r["after"] and r["after"] > r["before"])

    fmt = lambda v: f"{v:.2f}"  # noqa: E731
    lines = [
        f"Measured on {date.today().isoformat()} over {len(rows)} golden (sub-)questions against the bundled handbooks. "
        f"Embeddings: `{state.settings.embedding_model}`; re-ranker: `{state.settings.reranker_model}`; "
        f"FAISS returns k={k} candidates, and both orderings rank the same candidates.",
        "",
        "| Metric | FAISS only | FAISS + cross-encoder |",
        "|---|---|---|",
    ]
    for m in mb:
        lines.append(f"| {m} | {fmt(mb[m])} | **{fmt(ma[m])}** |")
    lines += [
        "",
        f"Re-ranking moved the gold section up for {better} question(s) and down for {worse}.",
        "",
    ]
    changed = [r for r in rows if r["faiss_top"] != r["rerank_top"]]
    lines += [f"**Questions where re-ranking changed the top result ({len(changed)} of {len(rows)}):**", ""]
    if changed:
        lines += ["| # | Question | FAISS #1 | Re-ranked #1 | Gold section |", "|---|---|---|---|---|"]
        for r in changed:
            mark = lambda sec: f"**{sec}** ✓" if sec == r["gold"] else str(sec)  # noqa: E731
            lines.append(f"| {r['id']} | {r['question']} | {mark(r['faiss_top'])} | {mark(r['rerank_top'])} "
                         f"| {r['gold']} |")
    else:
        lines.append("_None: FAISS and the cross-encoder agreed on every top result._")
    lines += [
        "",
        "<details><summary>Per-question ranks of the first gold-section chunk (lower is better)</summary>",
        "",
        "| # | Question | Gold section | FAISS rank | Re-ranked |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        b = r["before"] or "—"
        a = r["after"] or "—"
        arrow = ""
        if r["before"] and r["after"]:
            arrow = " ↑" if r["after"] < r["before"] else (" ↓" if r["after"] > r["before"] else "")
        lines.append(f"| {r['id']} | {r['question']} | {r['gold']} | {b} | {a}{arrow} |")
    lines += ["", "</details>"]
    table = "\n".join(lines)

    out = REPO / "docs" / "rerank_comparison.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("# Re-ranking: before vs after\n\n" + table + "\n", encoding="utf-8")
    print(table)
    print(f"\nWrote {out}")
    if not args.no_readme and update_readme("rerank", table):
        print("Updated README.md")


if __name__ == "__main__":
    main()
