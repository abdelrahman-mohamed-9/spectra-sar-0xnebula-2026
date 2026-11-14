import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_env import validate

class TestEnvironmentValidation(unittest.TestCase):
    def test_rejects_placeholders(self):
        errors = validate({"POSTGRES_PASSWORD":"CHANGE_ME", "MINIO_ROOT_USER":"CHANGE_ME", "MINIO_ROOT_PASSWORD":"CHANGE_ME"})
        self.assertEqual(len(errors), 3)
    def test_accepts_sample_valid_values(self):
        config = {"POSTGRES_PASSWORD":"demo-secret-example-123456", "MINIO_ROOT_USER":"local_admin", "MINIO_ROOT_PASSWORD":"another-local-secret-123456", "POSTGRES_PORT":"5432", "MINIO_PORT":"9000", "MINIO_CONSOLE_PORT":"9001"}
        self.assertEqual(validate(config), [])
    def test_rejects_duplicate_ports(self):
        config = {"POSTGRES_PASSWORD":"demo-secret-example-123456", "MINIO_ROOT_USER":"local_admin", "MINIO_ROOT_PASSWORD":"another-local-secret-123456", "POSTGRES_PORT":"9000", "MINIO_PORT":"9000"}
        self.assertTrue(any("unique" in x for x in validate(config)))
if __name__ == '__main__': unittest.main()
