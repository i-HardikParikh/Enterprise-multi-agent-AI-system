# ── Stage 1: API Runtime (Python 3.11) ──
FROM python:3.11-slim AS api
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
# Sync only core production dependencies (no dev group -> excludes aegra-cli)
RUN uv sync --frozen --no-dev
ENV HF_HOME=/app/.cache
# Pre-download HF models into the virtual env
RUN .venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
COPY . .
RUN mkdir -p data/uploads data/outputs data/faiss_index
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
CMD [".venv/bin/uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Stage 2: Aegra Runtime (Python 3.12) ──
FROM python:3.12-slim AS aegra
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
# Sync everything including dev group (includes aegra-cli)
RUN uv sync --frozen --all-groups
COPY . .
RUN mkdir -p data/uploads data/outputs data/faiss_index
CMD [".venv/bin/aegra", "dev"]
