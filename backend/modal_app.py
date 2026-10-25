"""Deploy the FastAPI backend to Modal (serverless containers, $30/month free credit).

One-time setup, from the repo root (inside the project's virtual environment):

    pip install modal
    modal setup                                              # log in through the browser
    modal secret create hr-policy-bot GOOGLE_API_KEY=your-key

Deploy (and re-deploy after every change):

    modal deploy backend/modal_app.py

Modal prints the URL, https://<your-workspace>--hr-policy-bot.modal.run. Put it in
Vercel as NEXT_PUBLIC_API_BASE.

How it runs:
- One container at most (max_containers=1), so uploads, the FAISS index and the
  RAGAS worker all live in the same process, as they do locally.
- It scales to zero after 10 idle minutes; the next request starts it again
  (about 20-40 seconds while models and the index load).
- /data is a Modal Volume, so the index, uploaded PDFs and ragas_eval.jsonl
  survive restarts and redeploys.
- The embedding and re-ranking models are downloaded at image build time.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import modal

BACKEND = Path(__file__).resolve().parent
REPO = BACKEND.parent
APP_ROOT = "/app"  # mirrors the repo layout: /app/backend, /app/frontend/out

data_volume = modal.Volume.from_name("hr-policy-bot-data", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    # CPU-only torch is ~2 GB smaller than the default CUDA build.
    .pip_install("torch", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install_from_requirements(str(BACKEND / "requirements.txt"))
    .env({
        "HF_HOME": "/models",
        "DATA_DIR": "/data",
        "SAMPLE_DIR": f"{APP_ROOT}/backend/data/sample",
        "TOKENIZERS_PARALLELISM": "false",
        "RAGAS_DO_NOT_TRACK": "true",
    })
    .add_local_dir(BACKEND / "app", f"{APP_ROOT}/backend/app", copy=True,
                   ignore=["**/__pycache__/**"])
    .add_local_dir(BACKEND / "scripts", f"{APP_ROOT}/backend/scripts", copy=True)
    .run_commands(f"cd {APP_ROOT}/backend && python scripts/prefetch_models.py")
    .add_local_dir(BACKEND / "data" / "sample", f"{APP_ROOT}/backend/data/sample")
)
# If the UI has been built locally (frontend/out), serve it from the same URL too.
if (REPO / "frontend" / "out" / "index.html").exists():
    image = image.add_local_dir(REPO / "frontend" / "out", f"{APP_ROOT}/frontend/out")

app = modal.App("hr-policy-bot", image=image)


@app.function(
    secrets=[modal.Secret.from_name("hr-policy-bot")],
    volumes={"/data": data_volume},
    cpu=1.0,
    memory=3072,
    min_containers=0,
    max_containers=1,
    scaledown_window=600,
    timeout=600,
)
@modal.concurrent(max_inputs=32)
@modal.asgi_app(label="hr-policy-bot")
def web():
    import sys

    sys.path.insert(0, f"{APP_ROOT}/backend")

    def commit_periodically() -> None:
        # Persist index, uploads and the eval log to the Volume.
        while True:
            time.sleep(20)
            try:
                data_volume.commit()
            except Exception:
                pass

    threading.Thread(target=commit_periodically, daemon=True).start()

    from app.main import app as fastapi_app

    return fastapi_app
