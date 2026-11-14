"""Run initial PostgreSQL schema in T02 environment; idempotent for fresh DB."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import db_connection


def main():
    sql = (Path(__file__).resolve().parents[1] / 'migrations' / '001_initial.sql').read_text()
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute('SELECT version FROM schema_migrations ORDER BY version')
            print('Applied schema versions:', [row[0] for row in cur.fetchall()])

if __name__ == '__main__':
    main()
