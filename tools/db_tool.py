"""
tools/db_tool.py — Database Query Tool

Uses SQLite for demo (swap connection string for PostgreSQL in production).
Auto-seeds demo sales + employees data on first run.
"""
import json
import re

import psycopg
import structlog
from langchain_core.tools import tool
from psycopg.rows import dict_row

logger = structlog.get_logger()


def _get_conn():
    from config import get_settings
    settings = get_settings()
    conn = psycopg.connect(settings.db_url, row_factory=dict_row)
    _seed(conn)
    return conn


def _seed(conn):
    """Seed demo tables if they don't exist in PostgreSQL."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY,
                product VARCHAR(100),
                region VARCHAR(50),
                revenue REAL,
                units INTEGER,
                date VARCHAR(20)
            );
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100),
                department VARCHAR(100),
                salary REAL,
                hire_date VARCHAR(20)
            );
        """)
        
        # Check sales
        cur.execute("SELECT COUNT(*) AS count FROM sales;")
        if cur.fetchone()["count"] == 0:
            cur.execute("""
                INSERT INTO sales (id, product, region, revenue, units, date) VALUES
                    (1,'Widget A','North',45000,300,'2024-01'),
                    (2,'Widget B','South',32000,200,'2024-01'),
                    (3,'Widget A','East', 67000,450,'2024-02'),
                    (4,'Widget C','West', 89000,600,'2024-02'),
                    (5,'Widget B','North',41000,280,'2024-03'),
                    (6,'Widget A','South',55000,370,'2024-03');
            """)
            
        # Check employees
        cur.execute("SELECT COUNT(*) AS count FROM employees;")
        if cur.fetchone()["count"] == 0:
            cur.execute("""
                INSERT INTO employees (id, name, department, salary, hire_date) VALUES
                    (1,'Alice Chen',  'Engineering',95000,'2022-03-15'),
                    (2,'Bob Smith',   'Marketing',  75000,'2021-07-01'),
                    (3,'Carol Jones', 'Engineering',105000,'2020-01-10'),
                    (4,'David Lee',   'Sales',      80000,'2023-05-20'),
                    (5,'Eve Wilson',  'HR',         70000,'2022-11-08');
            """)
        conn.commit()


@tool
def query_database(sql_query: str) -> str:
    """
    Execute a SQL SELECT query against the business database.

    Tables available:
      - sales(id, product, region, revenue, units, date)
      - employees(id, name, department, salary, hire_date)

    Only SELECT queries are allowed.

    Args:
        sql_query: A valid SQL SELECT statement

    Returns:
        Query results as JSON string
    """
    logger.info("query_database.called", query=sql_query[:100])
    
    # Strip SQL comments to prevent false positives and bypasses
    cleaned_query = re.sub(r"/\*.*?\*/", "", sql_query, flags=re.DOTALL)
    cleaned_query = re.sub(r"--.*?(?:\n|$)", "\n", cleaned_query).strip()

    if not cleaned_query.upper().startswith("SELECT"):
        return "Error: Only SELECT queries are permitted."
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(sql_query)
            rows = cur.fetchall()
        conn.close()
        if not rows:
            return "Query returned no results."
        return json.dumps([dict(r) for r in rows], indent=2, default=str)
    except Exception as e:
        return f"Database error: {e!s}"


@tool
def list_tables() -> str:
    """
    List all database tables and their column definitions.
    Always call this before writing queries.

    Returns:
    Table names with column names and types
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name != 'users';
            """)
            tables = [r[0] for r in cur.fetchall()]
            out = []
            for t in tables:
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = 'public';
                """, (t,))
                cols = cur.fetchall()
                col_str = ", ".join(f"{c[0]} ({c[1]})" for c in cols)
                out.append(f"Table: {t}\nColumns: {col_str}")
        conn.close()
        return "\n\n".join(out)
    except Exception as e:
        return f"Failed to list tables: {e!s}"


def get_db_tool():
    return [query_database, list_tables]
