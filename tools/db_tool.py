"""
tools/db_tool.py — Database Query Tool

Uses SQLite for demo (swap connection string for PostgreSQL in production).
Auto-seeds demo sales + employees data on first run.
"""
import sqlite3
import json
import structlog
from pathlib import Path
from langchain_core.tools import tool

logger = structlog.get_logger()
DB_PATH = "./data/enterprise.db"


def _get_conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed(conn)
    return conn


def _seed(conn):
    """Seed demo tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY,
            product TEXT, region TEXT,
            revenue REAL, units INTEGER, date TEXT
        );
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT, department TEXT,
            salary REAL, hire_date TEXT
        );
        INSERT OR IGNORE INTO sales VALUES
            (1,'Widget A','North',45000,300,'2024-01'),
            (2,'Widget B','South',32000,200,'2024-01'),
            (3,'Widget A','East', 67000,450,'2024-02'),
            (4,'Widget C','West', 89000,600,'2024-02'),
            (5,'Widget B','North',41000,280,'2024-03'),
            (6,'Widget A','South',55000,370,'2024-03');
        INSERT OR IGNORE INTO employees VALUES
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
    if not sql_query.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are permitted."
    try:
        conn = _get_conn()
        rows = conn.cursor().execute(sql_query).fetchall()
        conn.close()
        if not rows:
            return "Query returned no results."
        return json.dumps([dict(r) for r in rows], indent=2, default=str)
    except Exception as e:
        return f"Database error: {str(e)}"


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
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        out = []
        for t in tables:
            cols = cur.execute(f"PRAGMA table_info({t})").fetchall()
            col_str = ", ".join(f"{c[1]} ({c[2]})" for c in cols)
            out.append(f"Table: {t}\nColumns: {col_str}")
        conn.close()
        return "\n\n".join(out)
    except Exception as e:
        return f"Failed to list tables: {str(e)}"


def get_db_tool():
    return [query_database, list_tables]
