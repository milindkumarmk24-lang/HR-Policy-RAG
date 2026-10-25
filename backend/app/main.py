"""FastAPI entry point.

    uvicorn app.main:app --reload --reload-dir app --port 8000      (run from the backend/ folder)

Serves the JSON/SSE API under /api and, when frontend/out exists (after
`npm run build`), the web UI at /.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from contextlib import asynccontextmanager
from urllib.parse import quote
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .chain import ChatOptions
from .config import Settings, get_settings
from .ingest import chunk_body
from .schemas import ChatRequest
from .state import AppState, build_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hr_policy_bot")


def friendly_error(e: Exception, settings: Settings) -> str:
    msg = str(e)
    low = msg.lower()
    if "429" in msg or "resource_exhausted" in low or "quota" in low:
        return ("The Gemini API rate limit or daily quota was reached. Wait a minute and try again, "
                "or lower GEMINI_RPM in .env.")
    where = ("the hr-policy-bot Modal secret, then redeploy" if (os.environ.get("MODAL_IS_REMOTE") or os.environ.get("MODAL_TASK_ID"))
             else "GOOGLE_API_KEY in backend/.env, then restart the server")
    if "api key not valid" in low or "api_key_invalid" in low or "401" in msg:
        return f"Gemini rejected the API key as invalid. Check {where}."
    if "permission_denied" in low or "403" in msg:
        return ("Gemini refused the request (HTTP 403): the key may be restricted, or the Gemini API isn't enabled "
                f"for its Google Cloud project. Create a key at aistudio.google.com/apikey and update {where}.")
    if "404" in msg or ("not found" in low and "model" in low):
        return (f"The model '{settings.gemini_model}' isn't available for this key. "
                "Run `python scripts/list_models.py` and set GEMINI_MODEL in .env.")
    if "503" in msg or "unavailable" in low or "overloaded" in low:
        return "Gemini is temporarily overloaded (HTTP 503). Please try again shortly."
    return f"Something went wrong while answering: {type(e).__name__}."


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_app(state_factory: Callable[[], AppState] | None = None) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        factory = state_factory or (lambda: build_state(settings))
        state: AppState = await asyncio.to_thread(factory)
        app.state.rag = state
        state.evals.start()
        log.info("Ready: %d document(s), %d chunks, model=%s, key=%s", len(state.index.docs),
                 state.index.vector_count, state.settings.gemini_model, state.llm.available)
        yield
        await state.evals.stop()

    app = FastAPI(
        title="HR Policy Bot API",
        version="1.0.0",
        description="Single-source RAG over employee handbooks: FAISS + cross-encoder re-ranking + Gemini, "
                    "with per-query RAGAS evaluation.",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                       allow_origin_regex=settings.cors_origin_regex or None, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])

    def st(request: Request) -> AppState:
        return request.app.state.rag

    # ------------------------------------------------------------ health --
    @app.get("/health")
    async def health_basic():
        """Liveness probe: 200 as soon as the server is up."""
        return {"status": "ok"}

    @app.get("/api/health")
    async def health(request: Request):
        s = st(request)
        return {
            "status": "ok",
            "llm_model": s.settings.gemini_model,
            "judge_model": s.settings.judge_model_name,
            "embedding_model": s.settings.embedding_model,
            "reranker_model": s.settings.reranker_model if s.scorer else None,
            "has_api_key": s.llm.available,
            "eval_enabled": s.evals.enabled,
            "documents": len(s.index.docs),
            "chunks": s.index.vector_count,
            "rpm_limit": s.settings.gemini_rpm,
            "eval_queue": s.evals.queue.qsize(),
        }

    # --------------------------------------------------------- documents --
    @app.get("/api/documents")
    async def list_documents(request: Request):
        return {"documents": st(request).index.list_documents()}

    @app.post("/api/documents")
    async def upload_documents(request: Request, files: list[UploadFile] = File(...)):
        s = st(request)
        added, errors = [], []
        max_bytes = s.settings.max_upload_mb * 1024 * 1024
        for f in files:
            name = Path(f.filename or "document.pdf").name
            name = re.sub(r"[^\w.\- ()]+", "_", name)[:120] or "document.pdf"
            if len(s.index.docs) >= s.settings.max_documents:
                errors.append({"filename": name, "error": f"Limit of {s.settings.max_documents} documents reached."})
                continue
            data = await f.read(max_bytes + 1)
            if len(data) > max_bytes:
                errors.append({"filename": name, "error": f"File is larger than {s.settings.max_upload_mb} MB."})
                continue
            if not data.startswith(b"%PDF-"):
                errors.append({"filename": name, "error": "Not a PDF file."})
                continue
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=s.settings.uploads_dir) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)
            try:
                record = await asyncio.to_thread(s.index.add_pdf, tmp_path, name)
                added.append(record.public())
            except Exception as e:
                log.exception("Failed to index %s", name)
                errors.append({"filename": name, "error": str(e) if isinstance(e, ValueError)
                               else f"Could not read this PDF ({type(e).__name__})."})
            finally:
                tmp_path.unlink(missing_ok=True)
        status = 200 if added or not errors else 400
        return JSONResponse({"added": added, "errors": errors, "documents": s.index.list_documents()},
                            status_code=status)

    @app.post("/api/documents/sample")
    async def load_sample(request: Request):
        s = st(request)
        pdfs = s.settings.sample_pdfs
        if not pdfs:
            raise HTTPException(404, "No sample handbooks found")
        added = []
        for pdf in pdfs:
            record = await asyncio.to_thread(s.index.add_pdf, pdf, pdf.name, True)
            added.append(record.public())
        return {"added": added, "documents": s.index.list_documents()}

    @app.delete("/api/documents/{doc_id}")
    async def delete_document(request: Request, doc_id: str):
        s = st(request)
        if not await asyncio.to_thread(s.index.remove, doc_id):
            raise HTTPException(404, "Unknown document")
        return {"documents": s.index.list_documents()}

    @app.delete("/api/documents")
    async def reset_documents(request: Request):
        s = st(request)
        await asyncio.to_thread(s.index.reset)
        return {"documents": []}

    @app.get("/api/documents/{doc_id}/file")
    async def document_file(request: Request, doc_id: str):
        s = st(request)
        record = s.index.docs.get(doc_id)
        path = s.index.pdf_path(doc_id)
        if record is None or not path.exists():
            raise HTTPException(404, "Unknown document")
        ascii_name = record.filename.encode("ascii", "ignore").decode() or "document.pdf"
        disposition = f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(record.filename)}"
        return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": disposition})

    @app.get("/api/documents/{doc_id}/chunks")
    async def document_chunks(request: Request, doc_id: str, page: int | None = None):
        s = st(request)
        if doc_id not in s.index.docs:
            raise HTTPException(404, "Unknown document")
        chunks = s.index.chunks_for(doc_id)
        if page is not None:
            chunks = [c for c in chunks if c.metadata["page"] <= page <= c.metadata["page_end"]]
        return {"chunks": [{**{k: c.metadata.get(k) for k in ("chunk_id", "page", "page_end", "section",
                                                             "chapter", "category")},
                            "text": chunk_body(c)} for c in chunks]}

    # -------------------------------------------------------------- chat --
    def _options(req: ChatRequest) -> ChatOptions:
        o = req.options
        return ChatOptions(rerank=o.rerank, top_n=o.top_n, evaluate=o.evaluate, retrieval_only=o.retrieval_only)

    @app.post("/api/chat")
    async def chat(request: Request, body: ChatRequest):
        s = st(request)
        history = [t.model_dump() for t in body.history]
        try:
            async with s.llm.chat_priority():
                result = await s.pipeline.run(body.question, history, _options(body))
        except Exception as e:
            log.exception("chat failed")
            raise HTTPException(502, friendly_error(e, s.settings))
        result["eval"] = s.evals.submit(result, evaluate=body.options.evaluate)
        return result

    @app.post("/api/chat/stream")
    async def chat_stream(request: Request, body: ChatRequest):
        s = st(request)
        history = [t.model_dump() for t in body.history]

        async def events():
            try:
                async with s.llm.chat_priority():
                    prepared = await s.pipeline.prepare(body.question, history, _options(body))
                    preview = s.pipeline.finalize(prepared, "")
                    yield sse("plan", {"query_id": prepared.query_id, "mode": prepared.mode, "plan": preview["plan"]})
                    yield sse("retrieval", {"sources": preview["sources"], "retrieval": preview["retrieval"]})
                    parts: list[str] = []
                    async for token in s.pipeline.stream_answer(prepared):
                        parts.append(token)
                        yield sse("token", {"text": token})
                    result = s.pipeline.finalize(prepared, "".join(parts))
                result["eval"] = s.evals.submit(result, evaluate=body.options.evaluate)
                yield sse("done", result)
            except Exception as e:
                log.exception("chat stream failed")
                yield sse("error", {"message": friendly_error(e, s.settings)})

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ------------------------------------------------------------- evals --
    @app.get("/api/evals")
    async def list_evals(request: Request, limit: int = 50):
        s = st(request)
        return {"summary": s.evals.aggregate(), "records": s.evals.recent(min(max(limit, 1), 500))}

    @app.get("/api/evals/export")
    async def export_evals(request: Request):
        s = st(request)
        if not s.evals.log_path.exists():
            raise HTTPException(404, "No evaluations logged yet")
        return FileResponse(s.evals.log_path, media_type="application/x-ndjson", filename="ragas_eval.jsonl")

    @app.get("/api/evals/{query_id}")
    async def get_eval(request: Request, query_id: str):
        rec = st(request).evals.get(query_id)
        if rec is None:
            raise HTTPException(404, "Unknown query id")
        return rec

    @app.post("/api/evals/{query_id}/retry")
    async def retry_eval(request: Request, query_id: str):
        rec = st(request).evals.retry(query_id)
        if rec is None:
            raise HTTPException(400, "This query can't be re-evaluated")
        return rec

    # ---------------------------------------------------------- frontend --
    dist = settings.frontend_dist
    if dist.exists() and (dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    else:
        @app.get("/")
        async def root():
            return {"message": "HR Policy Bot API. The web UI isn't built: run `npm run build` in frontend/, "
                               "or open http://localhost:3000 with `npm run dev`. API docs: /docs"}

    return app


app = create_app()
