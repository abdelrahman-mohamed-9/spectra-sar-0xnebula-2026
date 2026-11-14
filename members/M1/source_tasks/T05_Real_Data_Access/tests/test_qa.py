"""Synthetic *software test fixtures only*, not NASA observations."""
import hashlib, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import verify_real_rasters as qa

class TestActualFileGates(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'reports').mkdir()
        self.patcher=patch.object(qa,'ROOT',self.root)
        self.patcher.start()
    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()
    def raster(self,role):
        import numpy as np, rasterio
        from rasterio.transform import from_bounds
        date,cmr=qa.EXPECTED[role]
        path=self.root/f'{role}_HHHH_{date}.tif'
        with rasterio.open(path,'w',driver='GTiff',height=24,width=32,count=1,
                           dtype='float32',crs='EPSG:4326',
                           transform=from_bounds(-134.7,58.33,-134.4,58.55,32,24),nodata=-9999) as ds:
            ds.write(np.ones((24,32),dtype='float32'),1)
            ds.set_band_description(1,'test scientific layer HHHH')
        return path
    def manifest(self,role,p,wrong_checksum=False):
        date,cmr=qa.EXPECTED[role]
        (self.root/'reports'/f'{role}-harmony-job.json').write_text(json.dumps({
            'status':'DOWNLOADED_NOT_SCIENCE_VALIDATED','cmr_granule_concept_id':cmr,
            'variable_requested':'/science/LSAR/GCOV/grids/frequencyA/HHHH',
            'normalized_geotiff':p.name,'original_geotiff_filename':f'nasa_{role}_HHHH_subset.tif',
            'sha256':'WRONG' if wrong_checksum else qa.hash_file(p)}))
    def test_no_raster_not_success(self):
        before=qa.inspect_tif(self.root/'no_before.tif','before')
        after=qa.inspect_tif(self.root/'no_after.tif','after')
        self.assertNotEqual(qa.validate_pair(before,after)['status'],'BASIC_PAIR_READY_FOR_M2')
    def test_renamed_file_is_not_provenance(self):
        b=self.raster('before');a=self.raster('after')
        report=qa.validate_pair(qa.inspect_tif(b,'before'),qa.inspect_tif(a,'after'))
        self.assertEqual(report['status'],'NEEDS_PROVENANCE_CONFIRMATION')
        self.assertFalse(report['source_provenance_verified'])
    def test_wrong_checksum_rejected(self):
        b=self.raster('before');a=self.raster('after')
        self.manifest('before',b)
        self.manifest('after',a,wrong_checksum=True)
        report=qa.validate_pair(qa.inspect_tif(b,'before'),qa.inspect_tif(a,'after'))
        self.assertEqual(report['status'],'NEEDS_PROVENANCE_CONFIRMATION')
    def test_verified_manifest_and_geotiffs(self):
        b=self.raster('before');a=self.raster('after')
        self.manifest('before',b);self.manifest('after',a)
        report=qa.validate_pair(qa.inspect_tif(b,'before'),qa.inspect_tif(a,'after'))
        self.assertEqual(report['status'],'BASIC_PAIR_READY_FOR_M2')
        self.assertTrue(report['source_provenance_verified'])
        self.assertFalse(report['science_flood_proven'])

if __name__ == '__main__': unittest.main()
