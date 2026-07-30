"""
tools/search_tool.py — Web Search Tool

Primary:  SerpAPI (if SERPAPI_API_KEY is set)
Fallback: DuckDuckGo (completely free, no key needed)
"""
import httpx
import structlog
from langchain_core.tools import tool

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@tool
def web_search(query: str) -> str:
    """
    Search the web for current information.
    Use for: real-time data, news, facts not in the knowledge base.

    Args:
        query: Search query string (be specific, 5-10 words ideal)

    Returns:
        Formatted search results as text
    """
    logger.info("web_search.called", query=query[:80])

    # Try SerpAPI if key available
    if settings.serpapi_api_key:
        try:
            resp = httpx.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": settings.serpapi_api_key, "num": 5},
                timeout=10,
            )
            data = resp.json()
            results = data.get("organic_results", [])
            if results:
                out = []
                for r in results[:5]:
                    out.append(
                        f"Title: {r.get('title', '')}\n"
                        f"URL: {r.get('link', '')}\n"
                        f"Summary: {r.get('snippet', '')}"
                    )
                return "\n\n---\n\n".join(out)
        except Exception as e:
            logger.warning("web_search.serpapi_failed", error=str(e))

    # Free fallback: DuckDuckGo
    try:
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=10,
            follow_redirects=True,
        )
        data = resp.json()
        parts = []
        if data.get("AbstractText"):
            parts.append(f"Summary: {data['AbstractText']}")
        if data.get("Answer"):
            parts.append(f"Answer: {data['Answer']}")
        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and topic.get("Text"):
                parts.append(f"- {topic['Text']}")
        if parts:
            return "\n\n".join(parts)
        return f"No results found for: {query}. Try rephrasing."
    except Exception as e:
        return f"Search unavailable: {e!s}. Use knowledge base instead."


def get_search_tool():
    return web_search
