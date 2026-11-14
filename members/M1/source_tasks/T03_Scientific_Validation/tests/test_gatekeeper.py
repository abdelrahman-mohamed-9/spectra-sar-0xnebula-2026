import copy
import json
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gatekeeper as g

SRC=Path(__file__).resolve().parents[1]/'inputs'/'selected-scenes.json'

class TestGatekeeper(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.selection=json.loads(SRC.read_text())

    def test_catalog_expected_pass_and_still_not_science_approved(self):
        r=g.validate_catalog(self.selection)
        self.assertEqual(r['catalog_status'],'PASS')
        self.assertFalse(r['science_approved'])
        self.assertEqual(r['assessment'],'CATALOG_PASS_RASTER_AND_SCIENCE_PENDING')

    def test_mismatched_track_fails(self):
        x=copy.deepcopy(self.selection)
        x['flood_gcOV_primary']['during_event']['name_metadata']['track']='777'
        r=g.validate_catalog(x)
        self.assertEqual(r['catalog_status'],'FAIL')
        self.assertTrue(any(c['name']=='GCOV.match_track' and c['outcome']=='FAIL' for c in r['checks']))

    def test_mismatched_crid_fails(self):
        x=copy.deepcopy(self.selection)
        a=x['flood_gcOV_primary']['during_event']
        a['granule_id']=a['granule_id'].replace('P05023','P05999')
        self.assertEqual(g.validate_catalog(x)['catalog_status'],'FAIL')

    def test_missing_product_id_fails(self):
        x=copy.deepcopy(self.selection)
        x['glacier_GOFF_primary']['cmr_concept_id']=''
        self.assertEqual(g.validate_catalog(x)['catalog_status'],'FAIL')

    def test_bad_time_order_fails(self):
        x=copy.deepcopy(self.selection)
        x['flood_gcOV_primary']['during_event']['acquisition_start_utc']='2026-08-02T12:00:00.000Z'
        self.assertEqual(g.validate_catalog(x)['catalog_status'],'FAIL')

    def test_no_files_is_pending_not_pass(self):
        self.assertEqual(g.inspect_pair(None,None)['status'],'PENDING')

    def test_missing_raster_fails(self):
        self.assertEqual(g.inspect_geotiff(Path('/nonexistent/this_should_not_exist.tif'))['status'],'FILE_MISSING')

    def test_valid_small_raster_grid_and_mismatch(self):
        try:
            import rasterio
            import numpy as np
            from rasterio.transform import from_origin
        except ImportError:
            self.skipTest('rasterio and numpy optional')
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as t:
            with rasterio.open(Path(t)/'a.tif','w',driver='GTiff',height=30,width=30,count=1,
                               dtype='float32',crs='EPSG:32608',transform=from_origin(100,200,20,20)) as ds:
                ds.write(np.ones((30,30),dtype='float32'),1)
            with rasterio.open(Path(t)/'b.tif','w',driver='GTiff',height=30,width=30,count=1,
                               dtype='float32',crs='EPSG:32608',transform=from_origin(100,200,20,20)) as ds:
                ds.write(np.ones((30,30),dtype='float32'),1)
            with rasterio.open(Path(t)/'c.tif','w',driver='GTiff',height=30,width=30,count=1,
                               dtype='float32',crs='EPSG:32608',transform=from_origin(120,200,20,20)) as ds:
                ds.write(np.ones((30,30),dtype='float32'),1)
            a=g.inspect_file(str(Path(t)/'a.tif'),'GCOV')
            b=g.inspect_file(str(Path(t)/'b.tif'),'GCOV')
            c=g.inspect_file(str(Path(t)/'c.tif'),'GCOV')
            self.assertEqual(g.inspect_pair(a,b)['status'],'PASS')
            self.assertEqual(g.inspect_pair(a,c)['status'],'REJECT')

if __name__=='__main__':
    unittest.main()
