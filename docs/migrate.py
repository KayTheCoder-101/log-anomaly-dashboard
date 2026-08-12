"""
Minimal database migration runner.

Not a full framework (no rollbacks, no branching) — deliberately lightweight
for this project's size. Tracks applied migrations in a `schema_migrations`
table so re-running this script is always safe: already-applied migrations
are skipped.

Usage:
    python3 migrate.py

Reads DATABASE_URL from the environment, falling back to the same local
default used elsewhere in this project.
"""
import os
import sys
from pathlib import Path

import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://admin:admin123@localhost:5432/logdb"
)
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def ensure_migrations_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT NOW()
        );
    """)


def get_applied(cur):
    cur.execute("SELECT filename FROM schema_migrations;")
    return {row[0] for row in cur.fetchall()}


def main():
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("No migration files found.")
        return

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            ensure_migrations_table(cur)
            conn.commit()

            applied = get_applied(cur)

        for path in migration_files:
            if path.name in applied:
                print(f"Skipping {path.name} (already applied)")
                continue

            print(f"Applying {path.name} ...")
            sql = path.read_text()
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s);",
                    (path.name,),
                )
            conn.commit()
            print(f"  done")

        print("All migrations up to date.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed, rolled back: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
