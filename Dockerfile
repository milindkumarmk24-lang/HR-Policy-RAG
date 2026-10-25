# One container: FastAPI serves the API and the pre-built Next.js UI.
# Built for Hugging Face Spaces (Docker SDK, port 7860, non-root user 1000),
# but runs anywhere:  docker build -t hr-policy-bot . && docker run -p 7860:7860 -e GOOGLE_API_KEY=... hr-policy-bot

# ---- 1. build the static frontend ------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. python runtime ---------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/user/.cache/huggingface \
    PORT=7860
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY backend/requirements.txt backend/requirements.txt
# CPU-only torch keeps the image ~2 GB smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
 && pip install -r backend/requirements.txt

COPY --chown=user backend/ backend/
COPY --from=web --chown=user /web/out frontend/out

USER user
# Bake the embedding + re-ranking models into the image so cold starts are fast.
RUN python backend/scripts/prefetch_models.py

WORKDIR /home/user/app/backend
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
