"""Read-only, real T03 PostgreSQL structural checks. Never inserts fake scenes."""
import os
import pytest

@pytest.mark.database
def test_required_tables_exist():
    dsn=os.environ.get('SPECTRA_DATABASE_URL')
    if not dsn:pytest.skip('Set SPECTRA_DATABASE_URL to running PostgreSQL')
    import psycopg
    expected={'sar_scenes','scene_pairs','processing_jobs','artifacts','change_results',
              'impact_assessments','alembic_version','audit_events','users','project_memberships'}
    with psycopg.connect(dsn,connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname=%s',('public',))
            actual={row[0] for row in cur.fetchall()}
    assert expected <= actual, f'Missing tables: {sorted(expected-actual)}'
