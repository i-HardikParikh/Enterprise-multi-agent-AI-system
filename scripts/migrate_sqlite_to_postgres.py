"""
scripts/migrate_sqlite_to_postgres.py — SQLite to PostgreSQL Migration Script with Validation Gates
"""
import sqlite3
import sys

import psycopg

# Add project root to sys.path
sys.path.append("F:\\Projects-Git\\Enterprise-multi-agent-AI-system")

from auth.models import create_users_table
from config import get_settings
from tools.db_tool import _get_conn


def migrate():
    settings = get_settings()
    sqlite_db_path = "data/enterprise.db"
    
    print("Starting database migration...")
    print(f"Source SQLite database: {sqlite_db_path}")
    print(f"Target PostgreSQL database: {settings.db_url}")
    
    # 1. Warm up target tables in PostgreSQL (ensures users, sales, and employees schemas exist)
    print("\nWarm up schemas in PostgreSQL...")
    create_users_table()
    pg_conn = _get_conn()
    pg_conn.close()
    
    # Connect to databases
    sq_conn = sqlite3.connect(sqlite_db_path)
    sq_conn.row_factory = sqlite3.Row
    sq_cur = sq_conn.cursor()
    
    pg_conn = psycopg.connect(settings.db_url)
    pg_cur = pg_conn.cursor()
    
    tables = ["users", "sales", "employees"]
    
    try:
        for t in tables:
            print(f"\nMigrating table: '{t}'...")
            
            # Fetch SQLite row count
            sq_cur.execute(f"SELECT COUNT(*) FROM {t};")
            sq_count = sq_cur.fetchone()[0]
            print(f"SQLite '{t}' row count: {sq_count}")
            
            # Fetch SQLite rows
            sq_cur.execute(f"SELECT * FROM {t};")
            rows = sq_cur.fetchall()
            
            # Truncate Postgres table
            print(f"Truncating PostgreSQL table '{t}'...")
            pg_cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE;")
            
            if not rows:
                print(f"Table '{t}' is empty in SQLite. Skipping row insertion.")
                continue
                
            # Perform batch insert
            cols = list(rows[0].keys())
            col_list = ", ".join(cols)
            val_placeholders = ", ".join(["%s"] * len(cols))
            insert_query = f"INSERT INTO {t} ({col_list}) VALUES ({val_placeholders});"
            
            records = []
            for r in rows:
                record = []
                for c in cols:
                    val = r[c]
                    # Map SQLite boolean/integer representations for users.is_active if needed
                    if t == "users" and c == "is_active":
                        val = bool(val)
                    record.append(val)
                records.append(record)
                
            print(f"Inserting {len(records)} records into PostgreSQL...")
            pg_cur.executemany(insert_query, records)
            pg_conn.commit()
            
            # PostgreSQL Count Validation Check
            pg_cur.execute(f"SELECT COUNT(*) FROM {t};")
            pg_count = pg_cur.fetchone()[0]
            print(f"PostgreSQL '{t}' row count: {pg_count}")
            
            # Validation Gate Check
            if sq_count != pg_count:
                print(f"\n[ERROR] ROW COUNT MISMATCH for table '{t}'! SQLite: {sq_count}, Postgres: {pg_count}")
                raise ValueError(f"Migration aborted due to row count mismatch in table: '{t}'")
                
            print(f"Successfully migrated table '{t}' with validation gate passed!")
            
        # Reset users table sequence to prevent unique key violation on auto-increment inserts
        print("Resetting PostgreSQL 'users_id_seq' auto-increment sequence...")
        pg_cur.execute("SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1));")
        pg_conn.commit()

        print("\n==============================================")
        print("[SUCCESS] All relational tables migrated and validated successfully!")
        print("==============================================")
        
    except Exception as e:
        print(f"\n[FATAL ERROR] Migration failed: {e!s}")
        print("Rolling back PostgreSQL transactions...")
        pg_conn.rollback()
        sys.exit(1)
    finally:
        sq_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    migrate()
