import sys, tempfile, pathlib, unittest, json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import fetch_harmony as f

class TestConfig(unittest.TestCase):
    def test_source_metadata(self):
        rows=f.load_selection()
        self.assertEqual(f.validate_configuration(rows),'C2854338529-ASF')
        self.assertEqual(rows['before']['source']['cmr_concept_id'],'G4319985062-ASF')
        self.assertEqual(rows['after']['source']['cmr_concept_id'],'G4338819270-ASF')
    def test_dates(self):
        rows=f.load_selection()
        self.assertEqual(rows['before']['date'],'20260920')
        self.assertEqual(rows['after']['date'],'20261002')
    def test_variable_bbox(self):
        self.assertEqual(f.VARIABLE,'/science/LSAR/GCOV/grids/frequencyA/HHHH')
        self.assertEqual(f.BBOX,(-134.70, 58.33, -134.40, 58.55))
    def test_saveload_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'rec.json';f.save_json(p,{'a':1});self.assertEqual(json.loads(p.read_text())['a'],1)

if __name__=='__main__':unittest.main()
