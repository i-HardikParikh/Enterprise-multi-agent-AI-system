"""
memory/vector_store.py — Vector Store + RAG Memory

FREE embeddings: HuggingFace sentence-transformers (no API key needed)
Supports:
  - FAISS     (local, free, no account)
  - Pinecone  (cloud, optional upgrade)

LangGraph node: retrieval_node
"""
import os
import structlog
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader, PyPDFLoader, CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings
from graph.state import AgentState

logger = structlog.get_logger()
settings = get_settings()


# ── FREE Embeddings (HuggingFace, runs locally) ───────────────────────────────

def get_embeddings():
    """
    Returns HuggingFace embeddings — 100% free, runs locally.
    Model: all-MiniLM-L6-v2 (fast, small, good quality)
    First run downloads the model (~90MB) automatically.
    """
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


# ── FAISS Vector Store ────────────────────────────────────────────────────────

class FAISSVectorStore:
    """Persistent local FAISS store — saves index to disk between runs."""

    def __init__(self):
        self.index_path = settings.faiss_index_path
        self._store = None
        Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)

    def _load_or_create(self):
        if self._store:
            return self._store

        embeddings = get_embeddings()

        if Path(self.index_path).exists():
            logger.info("faiss.loading_existing_index")
            self._store = FAISS.load_local(
                self.index_path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
        else:
            logger.info("faiss.creating_new_index")
            from langchain_core.documents import Document
            self._store = FAISS.from_documents(
                [Document(
                    page_content="Enterprise AI System Knowledge Base initialised.",
                    metadata={"source": "system_init"},
                )],
                embeddings,
            )
            self._store.save_local(self.index_path)

        return self._store

    def add_documents(self, file_path: str) -> int:
        ext = Path(file_path).suffix.lower()
        loader_map = {".pdf": PyPDFLoader, ".txt": TextLoader, ".csv": CSVLoader}
        loader_cls = loader_map.get(ext, TextLoader)
        docs = loader_cls(file_path).load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = splitter.split_documents(docs)

        store = self._load_or_create()
        store.add_documents(chunks)
        store.save_local(self.index_path)

        logger.info("faiss.documents_added", file=file_path, chunks=len(chunks))
        return len(chunks)

    def similarity_search(self, query: str, k: int = 4) -> list:
        store = self._load_or_create()
        return store.similarity_search(query, k=k)


# ── Pinecone Vector Store (optional upgrade) ──────────────────────────────────

class PineconeVectorStore:
    def __init__(self):
        from pinecone import Pinecone
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self._store = None

    def _get_store(self):
        if not self._store:
            # pyrefly: ignore [missing-import]
            from langchain_pinecone import PineconeVectorStore as LCPinecone
            self._store = LCPinecone(
                index=self.pc.Index(settings.pinecone_index_name),
                embedding=get_embeddings(),
            )
        return self._store

    def add_documents(self, file_path: str) -> int:
        docs = TextLoader(file_path).load()
        chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(docs)
        self._get_store().add_documents(chunks)
        return len(chunks)

    def similarity_search(self, query: str, k: int = 4) -> list:
        return self._get_store().similarity_search(query, k=k)


# ── Factory ───────────────────────────────────────────────────────────────────

def get_vector_store():
    if settings.vector_store == "pinecone":
        return PineconeVectorStore()
    return FAISSVectorStore()


# ── Redis Session Memory ──────────────────────────────────────────────────────

class RedisMemory:
    def __init__(self):
        import redis
        self.client = redis.from_url(settings.redis_url, decode_responses=True)
        self.ttl = settings.redis_ttl_seconds

    def save(self, session_id: str, key: str, value: str):
        self.client.setex(f"session:{session_id}:{key}", self.ttl, value)

    def get(self, session_id: str, key: str) -> str | None:
        return self.client.get(f"session:{session_id}:{key}")

    def get_summary(self, session_id: str) -> str:
        keys = self.client.keys(f"session:{session_id}:*")
        if not keys:
            return "No prior session history."
        parts = []
        for k in keys[-5:]:
            val = self.client.get(k)
            if val:
                parts.append(f"- {k.split(':')[-1]}: {val[:200]}")
        return "\n".join(parts)


_redis_memory = None

def get_redis_memory() -> RedisMemory | None:
    global _redis_memory
    if _redis_memory:
        return _redis_memory
    try:
        mem = RedisMemory()
        mem.client.ping()
        _redis_memory = mem
        return mem
    except Exception:
        logger.warning("redis.unavailable — running without session memory")
        return None


# ── LangGraph Node ────────────────────────────────────────────────────────────

def retrieval_node(state: AgentState) -> dict:
    """
    LangGraph node: Memory & RAG Retrieval
    Reads:  state.user_input, state.session_id
    Writes: state.retrieved_context, state.memory_summary
    """
    logger.info("retrieval_node.start")
    user_input = state["user_input"]
    session_id = state.get("session_id", "default")

    # 1. RAG retrieval
    retrieved_context = ""
    try:
        store = get_vector_store()
        docs = store.similarity_search(user_input, k=4)
        if docs:
            retrieved_context = "\n\n".join(
                f"[Source: {d.metadata.get('source', 'unknown')}]\n{d.page_content}"
                for d in docs
            )
            logger.info("retrieval_node.rag_done", num_docs=len(docs))
    except Exception as e:
        logger.warning("retrieval_node.rag_error", error=str(e))

    # 2. Session memory
    memory_summary = ""
    try:
        redis = get_redis_memory()
        if redis:
            memory_summary = redis.get_summary(session_id)
    except Exception as e:
        logger.warning("retrieval_node.memory_error", error=str(e))

    return {
        "retrieved_context": retrieved_context or "No relevant documents found.",
        "memory_summary": memory_summary or "No prior session context.",
        "step_history": [f"✅ Memory: Retrieved {len(retrieved_context)} chars of context"],
    }
