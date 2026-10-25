"""Print the chunks a PDF turns into: id, pages, section, category, length,
and the first words. Use it to check chunking before indexing.

    python scripts/inspect_chunks.py data/sample/Lumora_Employee_Handbook_2026.pdf
    python scripts/inspect_chunks.py path/to/handbook.pdf --full      # whole chunk text
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.ingest import chunk_body, chunk_pdf  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("pdf", type=Path)
ap.add_argument("--full", action="store_true", help="print the full text of every chunk")
args = ap.parse_args()

s = get_settings()
chunks, pages = chunk_pdf(args.pdf, "inspect", args.pdf.name, s.chunk_size, s.chunk_overlap)
print(f"{args.pdf.name}: {pages} pages -> {len(chunks)} chunks "
      f"(chunk_size={s.chunk_size} chars, overlap={s.chunk_overlap})\n")
for c in chunks:
    m = c.metadata
    pg = f"p.{m['page']}" + (f"-{m['page_end']}" if m["page_end"] != m["page"] else "")
    body = chunk_body(c)
    print(f"{m['chunk_index']:>4}  {pg:<9} {m['category'][:14]:<14} {(m['section'] or '-')[:46]:<46} {len(body):>5}c")
    print(("      " + body.replace("\n", "\n      ")) if args.full else f"      {body[:110].replace(chr(10), ' ')}")
lengths = [len(chunk_body(c)) for c in chunks]
print(f"\nchunk length: min {min(lengths)}, mean {sum(lengths) // len(lengths)}, max {max(lengths)} chars")
print("categories:", dict(Counter(c.metadata["category"] for c in chunks)))
