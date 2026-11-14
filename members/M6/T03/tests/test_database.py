import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import connection_kwargs, get_run, set_run_status


class DatabaseTests(unittest.TestCase):
    def test_config_host_for_host_process(self):
        e = {'POSTGRES_PASSWORD':'not-a-placeholder', 'POSTGRES_DB':'spectra_sar',
             'DB_HOST':'localhost', 'POSTGRES_PORT':'5432'}
        self.assertEqual(connection_kwargs(e)['host'], 'localhost')

    def test_placeholder_credentials_rejected(self):
        with self.assertRaises(ValueError):
            connection_kwargs({'POSTGRES_PASSWORD':'CHANGE_ME'})

    def test_get_run_missing(self):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = None
        self.assertIsNone(get_run(conn, uuid4()))

    def test_terminal_transition_rejected(self):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ('SUCCEEDED',)
        with self.assertRaises(ValueError):
            set_run_status(conn, uuid4(), 'RUNNING')

    def test_valid_transition(self):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = ('QUEUED',)
        set_run_status(conn, uuid4(), 'RUNNING')
        self.assertEqual(cur.execute.call_count, 2)

    def test_schema_tables_present(self):
        schema = (Path(__file__).resolve().parents[1] / 'database-schema.sql').read_text()
        for table in ('sar_scenes','processing_runs','run_scene_pairs','stage_executions',
                      'artifacts','artifact_inputs','analysis_results','audit_events'):
            self.assertIn('CREATE TABLE IF NOT EXISTS ' + table, schema)

if __name__ == '__main__':
    unittest.main()
