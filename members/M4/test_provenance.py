"""T03–T05 local integration/security tests; uses fake bytes, never claims SAR imagery."""
import json
from copy import deepcopy
import tempfile
import unittest
from pathlib import Path
from integrity import IntegrityError
from provenance import build_record, schema_validate, verify_record, write_record, load_json

SCENE={'scene_id':'S1A_TEST','provider':'Copernicus Data Space','product_type':'SLC','acquisition_time_utc':'2026-01-01T01:00:00Z','source_url':'https://dataspace.copernicus.eu/','orbit_direction':'ASCENDING','polarization':['VV']}
PRODUCER={'member':'M2','component':'change-detection','version':'0.1.0'}

class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'data'; self.root.mkdir()
        (self.root/'result.tif').write_bytes(b'LOCAL TEST DATA, not SAR imagery')
        self.record=build_record(root=self.root,files=['result.tif'],scenes=[deepcopy(SCENE)],producer=deepcopy(PRODUCER),algorithm='test-algorithm')
    def test_schema_accepts_generated_record(self):
        self.assertTrue(schema_validate(self.record))
    def test_verifies_untouched(self):
        self.assertEqual(verify_record(self.record,self.root)['status'],'PASS')
    def test_detects_tamper(self):
        (self.root/'result.tif').write_bytes(b'TAMPERED')
        self.assertEqual(verify_record(self.record,self.root)['status'],'FAIL')
    def test_detects_missing_file(self):
        (self.root/'result.tif').unlink()
        self.assertEqual(verify_record(self.record,self.root)['status'],'FAIL')
    def test_rejects_unknown_claim_artifact(self):
        self.record['claims']=[{'claim_id':'c1','statement':'change detected','supporting_artifact_ids':['nonexistent'],'confidence':0.5}]
        with self.assertRaises(IntegrityError): schema_validate(self.record)
    def test_rejects_invalid_digest(self):
        self.record['artifacts'][0]['sha256']='bad'
        with self.assertRaises(IntegrityError): schema_validate(self.record)
    def test_rejects_path_traversal(self):
        with self.assertRaises(IntegrityError):
            build_record(root=self.root,files=['../secrets'],scenes=[deepcopy(SCENE)],producer=deepcopy(PRODUCER),algorithm='test')
    def test_record_exclusive_creation(self):
        target=Path(self.tmp.name)/'evidence.json'
        write_record(self.record,target)
        with self.assertRaises(IntegrityError): write_record(self.record,target)
    def test_roundtrip_evidence(self):
        target=Path(self.tmp.name)/'evidence.json'
        write_record(self.record,target)
        self.assertEqual(verify_record(load_json(target),self.root)['status'],'PASS')
    def test_duplicate_json_keys_rejected(self):
        target=Path(self.tmp.name)/'bad.json'
        target.write_text('{"x": 1, "x": 2}')
        with self.assertRaises(IntegrityError): load_json(target)
    def test_verified_requires_baseline(self):
        self.record['integrity_status']='VERIFIED_AGAINST_BASELINE'
        with self.assertRaises(IntegrityError): schema_validate(self.record)
    def test_invalid_scene_metadata_rejected(self):
        self.record['source_scenes'][0]['polarization']=['INVALID']
        with self.assertRaises(IntegrityError): schema_validate(self.record)

if __name__=='__main__':unittest.main()
