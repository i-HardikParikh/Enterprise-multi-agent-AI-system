"""
config.py — Centralised settings loaded from .env

Supports 3 free LLM providers:
  - Groq    (cloud, free tier, fastest)
  - Gemini  (cloud, free 1500 req/day)
  - Ollama  (local, 100% free, no internet)
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    # ── LLM Provider ──────────────────────────────────────────────────────────
    llm_provider: str = Field(default="groq")

    # Groq
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    # Google Gemini
    google_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-1.5-flash")

    # Ollama (local)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.2")

    # ── Embeddings ────────────────────────────────────────────────────────────
    # Uses HuggingFace locally — no API key needed
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2"
    )

    # ── Vector Store ──────────────────────────────────────────────────────────
    vector_store: str = Field(default="pgvector")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379")
    redis_ttl_seconds: int = Field(default=3600)

    # ── LangSmith ─────────────────────────────────────────────────────────────
    langchain_tracing_v2: bool = Field(default=False)
    langchain_api_key: str = Field(default="")
    langchain_project: str = Field(default="enterprise-agent-system")

    # ── Langfuse ──────────────────────────────────────────────────────────────
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="http://localhost:4000")

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    max_retries: int = Field(default=3)
    max_iterations: int = Field(default=10)
    db_url: str = Field(default="postgresql://postgres:postgres@localhost:5434/enterprise_app")

    # ── Authentication ────────────────────────────────────────────────────────
    jwt_secret_key: str = Field(default="change-me-to-a-random-256-bit-secret")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_hours: int = Field(default=24)
    # Static API key for service-to-service / programmatic access.
    # Leave empty to disable static key auth (JWT only).
    api_key: str = Field(default="")

    # ── Tools ─────────────────────────────────────────────────────────────────
    serpapi_api_key: str = Field(default="")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
