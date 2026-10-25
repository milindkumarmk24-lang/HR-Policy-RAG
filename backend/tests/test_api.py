import json
import time

from fastapi.testclient import TestClient


def _client(make_settings, state_factory, monkeypatch, api_key=None):
    import app.main as main

    settings = make_settings(api_key=api_key)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    return TestClient(main.create_app(state_factory=lambda: state_factory(settings)))


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_health_and_documents(make_settings, state_factory, monkeypatch):
    with _client(make_settings, state_factory, monkeypatch) as c:
        h = c.get("/api/health").json()
        assert h["has_api_key"] is False and h["documents"] == 1 and h["chunks"] > 40
        docs = c.get("/api/documents").json()["documents"]
        assert docs[0]["is_sample"] is True
        doc_id = docs[0]["doc_id"]
        r = c.get(f"/api/documents/{doc_id}/file")
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        chunks = c.get(f"/api/documents/{doc_id}/chunks", params={"page": 4}).json()["chunks"]
        assert any(ch["section"] == "3.4 Sick Leave" for ch in chunks)


def test_upload_validation_delete_and_reset(make_settings, state_factory, monkeypatch, data_dir):
    with _client(make_settings, state_factory, monkeypatch) as c:
        r = c.post("/api/documents", files={"files": ("notes.txt", b"hello", "text/plain")})
        assert r.status_code == 400 and r.json()["errors"][0]["error"] == "Not a PDF file."
        doc_id = c.get("/api/documents").json()["documents"][0]["doc_id"]
        assert c.delete(f"/api/documents/{doc_id}").json()["documents"] == []
        assert c.get("/api/health").json()["chunks"] == 0
        # with no documents, chat explains what to do
        res = c.post("/api/chat", json={"question": "How many sick days?"}).json()
        assert res["mode"] == "no_documents"
        # re-upload the same PDF through the upload endpoint
        pdf = (data_dir / "sample" / "Lumora_Employee_Handbook_2026.pdf").read_bytes()
        r = c.post("/api/documents", files={"files": ("handbook.pdf", pdf, "application/pdf")})
        assert r.status_code == 200 and r.json()["added"][0]["filename"] == "handbook.pdf"
        assert c.delete("/api/documents").json()["documents"] == []


def test_chat_stream_and_eval_logging(make_settings, state_factory, monkeypatch, fake_llm):
    with _client(make_settings, state_factory, monkeypatch, api_key="test-key") as c:
        r = c.post("/api/chat/stream", json={"question": "How many paternity leave days do I get?"})
        assert r.status_code == 200
        events = _events(r.text)
        names = [e for e, _ in events]
        assert names[0] == "plan" and names[1] == "retrieval" and names[-1] == "done" and "token" in names
        done = events[-1][1]
        assert done["mode"] == "rag" and done["eval"]["eval_status"] == "queued"
        qid = done["query_id"]
        for _ in range(100):  # the background worker scores it
            status = c.get(f"/api/evals/{qid}").json()
            if status["eval_status"] not in ("queued", "running"):
                break
            time.sleep(0.1)
        assert status["eval_status"] in ("complete", "partial"), status
        listing = c.get("/api/evals").json()
        assert listing["records"][0]["query_id"] == qid
        assert listing["summary"]["evaluated"] == 1
        export = c.get("/api/evals/export")
        line = json.loads(export.text.strip().splitlines()[-1])
        assert line["query_id"] == qid and line["contexts"]
        assert list(line)[:5] == ["timestamp", "query_id", "question", "answer_preview", "metrics"]
        assert set(line["metrics"]) == {"faithfulness", "answer_relevancy", "context_precision", "context_recall"}
        assert line["metrics"]["faithfulness"] is not None and "scores" not in line


def test_chat_without_key_is_retrieval_only(make_settings, state_factory, monkeypatch):
    with _client(make_settings, state_factory, monkeypatch) as c:
        res = c.post("/api/chat", json={"question": "What is the hotel limit in Pune?"}).json()
        assert res["mode"] == "retrieval_only" and res["sources"]
        assert res["eval"]["eval_status"] == "skipped"
        bad = c.post("/api/chat", json={"question": ""})
        assert bad.status_code == 422


def test_unicode_filename_upload_and_download(make_settings, state_factory, monkeypatch, data_dir):
    with _client(make_settings, state_factory, monkeypatch) as c:
        c.delete("/api/documents")
        pdf = (data_dir / "sample" / "Lumora_Employee_Handbook_2026.pdf").read_bytes()
        r = c.post("/api/documents", files={"files": ("नीति हैंडबुक.pdf", pdf, "application/pdf")})
        assert r.status_code == 200, r.text
        doc_id = r.json()["added"][0]["doc_id"]
        f = c.get(f"/api/documents/{doc_id}/file")
        assert f.status_code == 200 and "filename*=UTF-8''" in f.headers["content-disposition"]
