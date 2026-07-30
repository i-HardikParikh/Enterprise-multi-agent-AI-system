"""
tools/rag_tool.py — RAG Knowledge Base Retrieval Tool
"""
import structlog
from langchain_core.tools import tool

logger = structlog.get_logger()


@tool
def rag_search(query: str) -> str:
    """
    Search the internal knowledge base for relevant documents.
    Use for: domain-specific info, uploaded reports, company documents.

    Args:
        query: Semantic search query

    Returns:
        Relevant document chunks with source info
    """
    from memory.vector_store import get_vector_store
    logger.info("rag_search.called", query=query[:80])

    try:
        store = get_vector_store()
        docs = store.similarity_search(query, k=4)
        if not docs:
            return "No relevant documents found in the knowledge base."
        results = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "unknown")
            results.append(f"[{i}] Source: {source}\n{doc.page_content}")
        return "\n\n---\n\n".join(results)
    except Exception as e:
        logger.error("rag_search.error", error=str(e))
        return f"Knowledge base search failed: {e!s}"


def get_rag_tool():
    return rag_search
