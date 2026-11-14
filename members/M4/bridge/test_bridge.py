import json, tempfile, hashlib, unittest
from pathlib import Path
from verify_m2_handoff import verify

class BridgeTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
 def tearDown(self): self.temp.cleanup()
 def seed(self, path='output.tif', digest=None):
  (self.root/'output.tif').write_bytes(b'example test-only payload')
  sha=hashlib.sha256(b'example test-only payload').hexdigest() if digest is None else digest
  (self.root/'m3-delivery.json').write_text(json.dumps({'schema_version':'1.0','producer':'SPECTRA-SAR-M2-T09','pair_id':'TEST','polarization':'VV','delivery_status':'EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED','scientific_approval':False,'limitations':['test-only'],'artifacts':{'mask':{'path':path,'sha256':sha}}}))
 def test_missing_delivery(self): self.assertEqual(verify(self.root)['reason'],'MISSING_M2_RUNTIME_DELIVERY_JSON')
 def test_valid(self):
  self.seed(); self.assertEqual(verify(self.root)['status'],'PASS')
 def test_tamper(self):
  self.seed(); (self.root/'output.tif').write_bytes(b'tampered'); self.assertEqual(verify(self.root)['status'],'FAIL')
 def test_path_traversal(self):
  self.seed(path='../output.tif'); self.assertEqual(verify(self.root)['status'],'FAIL')
 def test_invalid_sha(self):
  self.seed(digest='1234'); self.assertEqual(verify(self.root)['status'],'FAIL')
 def test_scientific_approval_not_accepted(self):
  self.seed(); p=self.root/'m3-delivery.json'; d=json.loads(p.read_text()); d['scientific_approval']=True; p.write_text(json.dumps(d)); self.assertEqual(verify(self.root)['status'],'FAIL')

if __name__=='__main__': unittest.main()
