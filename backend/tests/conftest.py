import os
import shutil
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
SAMPLE = BACKEND / "data" / "sample" / "Lumora_Employee_Handbook_2026.pdf"


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    (d / "sample").mkdir(parents=True)
    shutil.copy(SAMPLE, d / "sample" / SAMPLE.name)
    return d


@pytest.fixture()
def make_settings(data_dir, monkeypatch):
    def _make(api_key: str | None = None, **overrides):
        from app.config import Settings

        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        kw = dict(google_api_key=api_key, data_dir=data_dir, sample_dir=data_dir / "sample",
                  frontend_dist=data_dir / "no-frontend", _env_file=None)
        kw.update(overrides)
        return Settings(**kw)

    return _make


@pytest.fixture()
def fake_llm(monkeypatch):
    """Make LLMProvider hand out FakeGemini instead of calling Google."""
    from app.llm import LLMProvider

    from tests.fakes import FakeGemini

    monkeypatch.setattr(LLMProvider, "chat_model", lambda self, **kw: FakeGemini())
    return FakeGemini


@pytest.fixture()
def state_factory():
    def _factory(settings):
        from app.state import build_state

        from tests.fakes import HashingEmbeddings, LexicalScorer

        return build_state(settings, embeddings=HashingEmbeddings(), scorer=LexicalScorer())

    return _factory


os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
