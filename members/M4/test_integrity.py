"""Isolated T02 tests with explicitly synthetic local byte fixtures, not satellite data."""
import json
import tempfile
import unittest
from pathlib import Path
from integrity import IntegrityError, create_manifest, hash_file, verify_file, verify_manifest


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "data"
        self.root.mkdir()
        self.file = self.root / "example.tif"
        self.file.write_bytes(b"synthetic fixture, NOT a real SAR image\x00")
        self.manifest = self.base / "trusted" / "baseline.json"

    def test_hash_and_check(self):
        digest = hash_file(self.file)
        self.assertEqual(len(digest), 64)
        self.assertEqual(verify_file(self.file, digest)["status"], "PASS")

    def test_modified_bytes_fail(self):
        create_manifest(self.root, self.manifest, ["example.tif"])
        self.assertEqual(verify_manifest(self.root, self.manifest)["status"], "PASS")
        self.file.write_bytes(self.file.read_bytes() + b"tampered")
        self.assertEqual(verify_manifest(self.root, self.manifest)["status"], "FAIL")
        self.assertEqual(verify_manifest(self.root, self.manifest)["results"][0]["reason"], "HASH_MISMATCH")

    def test_missing_file_fails(self):
        create_manifest(self.root, self.manifest, ["example.tif"])
        self.file.unlink()
        self.assertEqual(verify_manifest(self.root, self.manifest)["status"], "FAIL")

    def test_bad_hash_fails_closed(self):
        self.assertEqual(verify_file(self.file, "")["reason"], "INVALID_EXPECTED_DIGEST")

    def test_traversal_rejected(self):
        with self.assertRaises(IntegrityError):
            create_manifest(self.root, self.manifest, ["../something"])

    def test_symlink_rejected(self):
        (self.root / "link.tif").symlink_to(self.file)
        with self.assertRaises(IntegrityError):
            create_manifest(self.root, self.manifest, ["link.tif"])

    def test_no_manifest_overwrite(self):
        create_manifest(self.root, self.manifest, ["example.tif"])
        with self.assertRaises(IntegrityError):
            create_manifest(self.root, self.manifest, ["example.tif"])

    def test_tampered_baseline_digest_rejected(self):
        create_manifest(self.root, self.manifest, ["example.tif"])
        data = json.loads(self.manifest.read_text())
        data["artifacts"][0]["sha256"] = "not a digest"
        self.manifest.write_text(json.dumps(data))
        with self.assertRaises(IntegrityError):
            verify_manifest(self.root, self.manifest)

    def test_duplicate_json_key_rejected(self):
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text('{"schema_version":"1.0","algorithm":"sha256","algorithm":"sha256","artifacts":[]}')
        with self.assertRaises(IntegrityError):
            verify_manifest(self.root, self.manifest)


if __name__ == "__main__":
    unittest.main()
