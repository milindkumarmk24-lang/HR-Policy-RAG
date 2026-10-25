"""Shared helpers for the offline evaluation scripts."""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.config import Settings, get_settings  # noqa: E402
from app.state import AppState, build_state  # noqa: E402

GOLDEN = BACKEND / "eval" / "golden_set.jsonl"
RESULTS = BACKEND / "eval" / "results"


def load_golden(path: Path = GOLDEN) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def eval_state(**overrides) -> AppState:
    """A fresh app state over the bundled sample handbooks, with its own
    temporary index, so the scripts never touch the index the web app uses."""
    base = get_settings()
    tmp = Path(tempfile.mkdtemp(prefix="hrbot-eval-")) / "data"
    settings = Settings(**{**base.model_dump(), "data_dir": tmp, "sample_dir": base.sample_dir,
                           "autoload_sample": True, **overrides})
    return build_state(settings)


def sub_queries(item: dict) -> list[tuple[str, list[str]]]:
    """(question, gold sections) pairs. Multi-part items are split using the
    reference sub-questions, each paired with its own gold section."""
    if item["type"] == "summary":
        return [(item["question"], item["gold_sections"])]  # any of the area's sections counts
    if item.get("sub_questions"):
        return [(q, [s]) for q, s in zip(item["sub_questions"], item["gold_sections"])]
    return [(item["question"], item["gold_sections"])]


def update_readme(marker: str, content: str, readme: Path = REPO / "README.md") -> bool:
    if not readme.exists():
        return False
    text = readme.read_text(encoding="utf-8")
    pattern = re.compile(rf"(<!-- BEGIN:{marker} -->\n).*?(\n<!-- END:{marker} -->)", re.DOTALL)
    if not pattern.search(text):
        return False
    readme.write_text(pattern.sub(lambda m: m.group(1) + content.strip() + m.group(2), text), encoding="utf-8")
    return True
