"""query_index(question, k): show the top-k chunks FAISS returns for a
question, optionally re-ranked. Uses the same index as the web app.

    python scripts/query_index.py "How many sick days do I get?"
    python scripts/query_index.py "How many sick days do I get?" -k 8 --rerank
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.state import build_state  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("question")
ap.add_argument("-k", type=int, default=5)
ap.add_argument("--rerank", action="store_true", help="also show the cross-encoder order")
args = ap.parse_args()

state = build_state(get_settings(), load_reranker=args.rerank)
print(f"\nFAISS top-{args.k} for: {args.question!r}\n")
for r in state.index.query_index(args.question, args.k):
    print(f"  {r['rank']:>2}. cos={r['score']:.4f}  p.{r['page']:<3} {(r['section'] or '-')[:40]:<40}  {r['snippet'][:70]}")

if args.rerank:
    sub = state.retriever.retrieve_one(args.question, keep=args.k, rerank=True, fetch_k=max(args.k, 12))
    print(f"\nAfter cross-encoder re-ranking ({state.settings.reranker_model}):\n")
    for c in sub.candidates[: args.k]:
        m = c.doc.metadata
        print(f"  {c.rerank_rank:>2}. (FAISS #{c.faiss_rank:<2}) relevance={c.relevance:.3f}  p.{m['page']:<3} "
              f"{(m.get('section') or '-')[:40]}")
