"""
memory/vector_store.py — Vector Store + RAG Memory using PostgreSQL pgvector
"""
import os
import json
import structlog
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

from langchain_community.document_loaders import TextLoader, PyPDFLoader, CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

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


# ── PostgreSQL pgvector Store ──────────────────────────────────────────────────

class PGVectorStore:
    """Persistent pgvector store in PostgreSQL."""

    def __init__(self):
        self.embeddings = get_embeddings()

    def _get_conn(self) -> psycopg.Connection:
        from config import get_settings
        settings = get_settings()
        conn = psycopg.connect(settings.db_url, row_factory=dict_row)
        return conn

    def setup(self):
        """Create vector extension, table, and HNSW index if they don't exist."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        id SERIAL PRIMARY KEY,
                        content TEXT NOT NULL,
                        metadata JSONB,
                        embedding VECTOR(384)
                    );
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS embeddings_hnsw_idx 
                    ON embeddings USING hnsw (embedding vector_cosine_ops);
                """)
                conn.commit()
        finally:
            conn.close()

    def add_documents(self, file_path: str) -> int:
        self.setup()
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
        if not chunks:
            return 0

        texts = [c.page_content for c in chunks]
        vectors = self.embeddings.embed_documents(texts)

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                for chunk, vector in zip(chunks, vectors):
                    meta = chunk.metadata.copy()
                    if "source" not in meta:
                        meta["source"] = Path(file_path).name
                    cur.execute(
                        "INSERT INTO embeddings (content, metadata, embedding) VALUES (%s, %s, %s);",
                        (chunk.page_content, json.dumps(meta), vector)
                    )
                conn.commit()
        finally:
            conn.close()

        logger.info("pgvector.documents_added", file=file_path, chunks=len(chunks))
        return len(chunks)

    def similarity_search(self, query: str, k: int = 4) -> list:
        self.setup()
        query_vector = self.embeddings.embed_query(query)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                # Seed with initial document if table is empty
                cur.execute("SELECT COUNT(*) AS count FROM embeddings;")
                if cur.fetchone()["count"] == 0:
                    initial_content = "Enterprise AI System Knowledge Base initialised."
                    initial_vector = self.embeddings.embed_query(initial_content)
                    cur.execute(
                        "INSERT INTO embeddings (content, metadata, embedding) VALUES (%s, %s, %s);",
                        (initial_content, json.dumps({"source": "system_init"}), initial_vector)
                    )
                    conn.commit()

                cur.execute(
                    "SELECT content, metadata FROM embeddings ORDER BY embedding <=> %s::vector LIMIT %s;",
                    (query_vector, k)
                )
                rows = cur.fetchall()
                return [Document(page_content=r["content"], metadata=r["metadata"]) for r in rows]
        finally:
            conn.close()


# ── Factory ───────────────────────────────────────────────────────────────────

def get_vector_store():
    return PGVectorStore()


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
    user_input = state.get("user_input", "")
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
