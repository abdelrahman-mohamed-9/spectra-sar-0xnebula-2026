import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import db_connection

TABLES = ('sar_scenes','processing_runs','run_scene_pairs','stage_executions',
          'artifacts','artifact_inputs','analysis_results','audit_events','schema_migrations')

def main():
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT current_database(), current_user, version()')
            name, user, version = cur.fetchone()
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            present = {r[0] for r in cur.fetchall()}
            missing = set(TABLES) - present
            print(f'Database={name}, user={user}, PostgreSQL={version.split()[1]}')
            print('Tables present:', len(set(TABLES) & present), '/', len(TABLES))
            if missing:
                raise SystemExit(f'Missing tables: {sorted(missing)}')
            cur.execute('SELECT version FROM schema_migrations')
            print('Migrations:', [row[0] for row in cur.fetchall()])

if __name__ == '__main__':
    main()
