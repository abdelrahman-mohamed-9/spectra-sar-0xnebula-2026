import tempfile, unittest, json, hashlib
from pathlib import Path
from integrate_m2_m4 import main

class IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.data=self.root/'data'; self.data.mkdir(); self.reports=self.root/'reports'
 def tearDown(self): self.tmp.cleanup()
 def make_handoff(self, wrong=False):
  f=self.data/'change.tif';f.write_bytes(b'TEST FIXTURE - NOT SAR DATA')
  h=hashlib.sha256(f.read_bytes()).hexdigest()
  doc={'schema_version':'1.0','producer':'SPECTRA-SAR-M2-T09','pair_id':'TEST_ONLY','polarization':'VV','delivery_status':'EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED','scientific_approval':False,'limitations':['test-only'],'artifacts':{'change':{'path':f.name,'sha256':('0'*64) if wrong else h}}}
  (self.data/'m3-delivery.json').write_text(json.dumps(doc))
 def test_missing_runtime(self):
  self.assertEqual(main(['--m2-output',str(self.data),'--reports',str(self.reports)]),1)
  s=json.loads((self.reports/'integration_status.json').read_text());self.assertEqual(s['integrity'],'FAIL')
 def test_valid_integrity_only(self):
  self.make_handoff(); self.assertEqual(main(['--m2-output',str(self.data),'--reports',str(self.reports)]),0)
  s=json.loads((self.reports/'integration_status.json').read_text());self.assertEqual(s['evidence'],'NOT_CREATED');self.assertFalse(s['scientific_approval'])
 def test_tamper(self):
  self.make_handoff(wrong=True);self.assertEqual(main(['--m2-output',str(self.data),'--reports',str(self.reports)]),1)
 def test_reject_fake_source_metadata(self):
  self.make_handoff()
  fake=self.root/'source.json';fake.write_text(json.dumps({'source_scenes':[{'scene_id':'<UNKNOWN>'}]*2}))
  self.assertEqual(main(['--m2-output',str(self.data),'--reports',str(self.reports),'--source-metadata',str(fake)]),1)

if __name__=='__main__': unittest.main()
