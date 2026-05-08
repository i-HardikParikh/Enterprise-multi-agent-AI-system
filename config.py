"""
config.py — Centralised settings loaded from .env

Supports 3 free LLM providers:
  - Groq    (cloud, free tier, fastest)
  - Gemini  (cloud, free 1500 req/day)
  - Ollama  (local, 100% free, no internet)
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # ── LLM Provider ──────────────────────────────────────────────────────────
    llm_provider: str = Field(default="groq", env="LLM_PROVIDER")

    # Groq
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", env="GROQ_MODEL")

    # Google Gemini
    google_api_key: str = Field(default="", env="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-flash", env="GEMINI_MODEL")

    # Ollama (local)
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2", env="OLLAMA_MODEL")

    # ── Embeddings ────────────────────────────────────────────────────────────
    # Uses HuggingFace locally — no API key needed
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        env="EMBEDDING_MODEL",
    )

    # ── Vector Store ──────────────────────────────────────────────────────────
    vector_store: str = Field(default="faiss", env="VECTOR_STORE")
    faiss_index_path: str = Field(default="./data/faiss_index", env="FAISS_INDEX_PATH")
    pinecone_api_key: str = Field(default="", env="PINECONE_API_KEY")
    pinecone_environment: str = Field(default="us-east-1", env="PINECONE_ENVIRONMENT")
    pinecone_index_name: str = Field(default="enterprise-agent", env="PINECONE_INDEX_NAME")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    redis_ttl_seconds: int = Field(default=3600, env="REDIS_TTL_SECONDS")

    # ── LangSmith ─────────────────────────────────────────────────────────────
    langchain_tracing_v2: bool = Field(default=False, env="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", env="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="enterprise-agent-system", env="LANGCHAIN_PROJECT")

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = Field(default="development", env="APP_ENV")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    max_iterations: int = Field(default=10, env="MAX_ITERATIONS")

    # ── Tools ─────────────────────────────────────────────────────────────────
    serpapi_api_key: str = Field(default="", env="SERPAPI_API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
