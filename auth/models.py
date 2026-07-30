"""
auth/models.py — PostgreSQL users table management.
"""
import psycopg
import structlog
from psycopg.rows import dict_row

logger = structlog.get_logger()


def get_db() -> psycopg.Connection:
    """Return a connected psycopg Connection with dict row factory."""
    from config import get_settings
    settings = get_settings()
    conn = psycopg.connect(settings.db_url, row_factory=dict_row)
    return conn


def create_users_table() -> None:
    """Create the users table if it doesn't already exist in PostgreSQL.

    Called once on application startup via the FastAPI lifespan hook.
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id               SERIAL PRIMARY KEY,
                    username         VARCHAR(255) UNIQUE NOT NULL,
                    email            VARCHAR(255) UNIQUE NOT NULL,
                    hashed_password  VARCHAR(255) NOT NULL,
                    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            logger.info("auth.create_users_table_success")
    except Exception as e:
        logger.error("auth.create_users_table_failed", error=str(e))
        raise
    finally:
        conn.close()
