import json
import tempfile
import unittest
import uuid
from pathlib import Path
from copy import deepcopy

from provenance import ProvenanceError, make_manifest, validate_manifest, verify_local_artifacts
from integrity_validator import IntegrityError, hash_file, local_path_from_uri, verify_file

class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'raw.bin').write_bytes(b'local deterministic test bytes; NOT satellite imagery')
        digest, size = hash_file(self.root/'raw.bin')
        self.scene = {'id':str(uuid.uuid4()), 'provider':'TEST_PROVIDER',
                      'provider_scene_id':'fixture-only', 'provider_record_url':'https://example.org/record',
                      'source_license':'test-only'}
        self.art = {'id':str(uuid.uuid4()), 'scene_id':self.scene['id'], 'run_id':None,
                    'artifact_type':'TEST_FIXTURE', 'storage_uri':'file://raw.bin',
                    'sha256':digest, 'bytes_size':size, 'producer_component':'M1', 'input_artifact_ids':[]}
        self.manifest = make_manifest(scenes=[self.scene], artifacts=[self.art], created_at='2026-11-13T00:00:00Z')

    def test_roundtrip_digest(self): self.assertTrue(validate_manifest(self.manifest))
    def test_verify_real_local_bytes(self): self.assertTrue(verify_local_artifacts(self.manifest, root=self.root)['all_artifacts_verified'])
    def test_detect_tampered_manifest(self):
        doc=deepcopy(self.manifest); doc['artifacts'][0]['artifact_type']='ALTERED'
        with self.assertRaisesRegex(ProvenanceError,'digest mismatch'): validate_manifest(doc)
    def test_detect_tampered_file(self):
        (self.root/'raw.bin').write_bytes(b'changed!')
        with self.assertRaises(IntegrityError): verify_local_artifacts(self.manifest, root=self.root)
    def test_detect_missing_parent(self):
        self.art['input_artifact_ids']=[str(uuid.uuid4())]
        with self.assertRaisesRegex(ProvenanceError,'missing input'): make_manifest(scenes=[self.scene],artifacts=[self.art])
    def test_detect_lineage_cycle(self):
        a=deepcopy(self.art); b=deepcopy(self.art)
        b['id']=str(uuid.uuid4()); b['input_artifact_ids']=[a['id']]; a['input_artifact_ids']=[b['id']]
        with self.assertRaisesRegex(ProvenanceError,'cycle'): make_manifest(scenes=[self.scene], artifacts=[a,b])
    def test_detect_duplicate_ids(self):
        with self.assertRaisesRegex(ProvenanceError,'duplicate artifact id'): make_manifest(scenes=[self.scene],artifacts=[self.art,self.art])
    def test_prevent_root_escape(self):
        with self.assertRaises(IntegrityError): local_path_from_uri('file://../secret',root=self.root)
    def test_prevent_absolute_path(self):
        with self.assertRaises(IntegrityError): local_path_from_uri('file:///etc/passwd',root=self.root)
    def test_reject_non_https_provider_url(self):
        scene={**self.scene, 'provider_record_url':'http://example.org'}
        with self.assertRaises(ProvenanceError): make_manifest(scenes=[scene],artifacts=[self.art])
    def test_remote_explicitly_unverified(self):
        art={**self.art,'storage_uri':'s3://bucket/remote.tif'}
        manifest=make_manifest(scenes=[self.scene],artifacts=[art])
        outcome=verify_local_artifacts(manifest,root=self.root)
        self.assertFalse(outcome['all_artifacts_verified'])
        self.assertEqual(outcome['not_verified_remote'],1)
    def test_correct_checksum_wrong_length(self):
        with self.assertRaises(IntegrityError): verify_file(self.root/'raw.bin', self.art['sha256'], self.art['bytes_size']+1)
    def test_bad_timestamp(self):
        with self.assertRaises(ProvenanceError): make_manifest(scenes=[self.scene],artifacts=[self.art],created_at='2026-11-13')
    def test_valid_2_node_lineage(self):
        out={**self.art,'id':str(uuid.uuid4()),'scene_id':None,'run_id':str(uuid.uuid4()),
             'producer_component':'M2','input_artifact_ids':[self.art['id']]}
        self.assertTrue(validate_manifest(make_manifest(scenes=[self.scene],artifacts=[self.art,out])))

if __name__ == '__main__': unittest.main()
