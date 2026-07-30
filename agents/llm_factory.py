"""
agents/llm_factory.py — LLM Factory

Supports 3 FREE providers — switch via LLM_PROVIDER in .env:

  groq   → Groq cloud (free, fastest, best for agents)
  gemini → Google Gemini Flash (free 1500 req/day)
  ollama → Local Ollama (100% free, runs on your machine)

Usage:
    llm = get_llm()               # default settings
    llm = get_llm(temperature=0.3, streaming=True)
"""
import structlog

from config import get_settings

logger = structlog.get_logger()
_settings = get_settings()


def get_llm(temperature: float = 0.0, streaming: bool = False):
    """
    Returns a configured LangChain chat model based on LLM_PROVIDER in .env.

    Args:
        temperature: 0.0 = deterministic/factual, 0.3+ = more creative
        streaming:   Enable token streaming (for SSE endpoints)

    Returns:
        LangChain BaseChatModel instance
    """
    provider = _settings.llm_provider.lower()
    logger.debug("llm_factory.get_llm", provider=provider, temperature=temperature)

    # ── Groq (Recommended: free, fast, great for agents) ──────────────────────
    if provider == "groq":
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                api_key=_settings.groq_api_key,
                model=_settings.groq_model,
                temperature=temperature,
                streaming=streaming,
                max_retries=2,
            )
        except ImportError:
            raise ImportError(
                "Groq not installed. Run: uv add langchain-groq"
            )

    # ── Google Gemini (free 1500 req/day) ─────────────────────────────────────
    elif provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=_settings.gemini_model,
                google_api_key=_settings.google_api_key,
                temperature=temperature,
                streaming=streaming,
                convert_system_message_to_human=True,  # Gemini quirk
            )
        except ImportError:
            raise ImportError(
                "Google GenAI not installed. Run: uv add langchain-google-genai"
            )

    # ── Ollama (100% local, no internet, no API key) ───────────────────────────
    elif provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=_settings.ollama_model,
                base_url=_settings.ollama_base_url,
                temperature=temperature,
                num_predict=2048,
            )
        except ImportError:
            # Fallback to community package
            from langchain_community.chat_models import ChatOllama
            return ChatOllama(
                model=_settings.ollama_model,
                base_url=_settings.ollama_base_url,
                temperature=temperature,
            )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            f"Choose one of: groq, gemini, ollama"
        )


def get_provider_info() -> dict:
    """Returns info about the currently configured provider — useful for /health endpoint."""
    provider = _settings.llm_provider.lower()
    info = {
        "groq":   {"model": _settings.groq_model,   "type": "cloud_free"},
        "gemini": {"model": _settings.gemini_model,  "type": "cloud_free"},
        "ollama": {"model": _settings.ollama_model,  "type": "local_free"},
    }
    return {
        "provider": provider,
        **info.get(provider, {"model": "unknown", "type": "unknown"}),
    }
