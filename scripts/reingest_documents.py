"""
scripts/reingest_documents.py — Re-ingestion script for pgvector storage
"""
import sys
from pathlib import Path

import psycopg

# Add project root to sys.path
sys.path.append("F:\\Projects-Git\\Enterprise-multi-agent-AI-system")

from config import get_settings
from memory.vector_store import get_vector_store


def reingest():
    settings = get_settings()
    uploads_dir = Path("data/uploads")
    
    print("Initializing Postgres pgvector database...")
    store = get_vector_store()
    store.setup()
    
    # Connect to check rows
    conn = psycopg.connect(settings.db_url)
    cur = conn.cursor()
    
    try:
        # Clear existing embeddings to ensure clean migration state
        print("Clearing existing embeddings in PostgreSQL...")
        cur.execute("TRUNCATE TABLE embeddings RESTART IDENTITY;")
        conn.commit()
        
        # Scan uploads directory
        files = []
        if uploads_dir.exists():
            files = [f for f in uploads_dir.iterdir() if f.is_file() and f.name != ".gitkeep"]
            
        if files:
            print(f"Found {len(files)} files in 'data/uploads' for re-ingestion.")
            total_chunks = 0
            for f in files:
                print(f"Ingesting file: {f.name}...")
                chunks_added = store.add_documents(str(f))
                total_chunks += chunks_added
                print(f"Added {chunks_added} chunks for {f.name}.")
                
            # Verification check
            cur.execute("SELECT COUNT(*) FROM embeddings;")
            db_count = cur.fetchone()[0]
            print(f"\nVerification: Ingested {len(files)} files into {db_count} total chunks.")
            if db_count != total_chunks:
                raise ValueError(f"Verification mismatch! Expected {total_chunks} chunks, found {db_count} in DB.")
        else:
            print("No files found in 'data/uploads'. Initializing with system default seed document...")
            # Trigger standard seed check in similarity_search or direct insert
            store.similarity_search("initialize seed query", k=1)
            
            cur.execute("SELECT COUNT(*) FROM embeddings;")
            db_count = cur.fetchone()[0]
            print(f"PostgreSQL embeddings count: {db_count}")
            assert db_count == 1, f"Expected exactly 1 seed chunk, found {db_count}"
            
        print("\n==============================================")
        print("[SUCCESS] pgvector Re-ingestion and Validation passed successfully!")
        print("==============================================")
        
    except Exception as e:
        print(f"\n[FATAL ERROR] Re-ingestion failed: {e!s}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    reingest()
