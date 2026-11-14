import json
import numpy as np
import pytest
import rasterio
from change_detector import log_ratio_db, classify_ratio, run_detection
from test_t02 import fixture


def test_equal_power_no_change():
    b=np.ones((2,2),dtype='float32')
    s=log_ratio_db(b,b,np.ones_like(b,dtype=bool))
    assert np.allclose(s,0)
    assert np.all(classify_ratio(s)==0)


def test_increase_by_3db():
    b=np.full((3,3),.25,dtype='float32');a=b*2
    s=log_ratio_db(b,a,np.ones_like(b,dtype=bool))
    assert np.allclose(s,3.0102999566,atol=1e-5)
    assert np.all(classify_ratio(s,3.0)==2)


def test_decrease_by_3db():
    b=np.full((2,2),.5,dtype='float32');a=b/2
    assert np.all(classify_ratio(log_ratio_db(b,a,np.ones_like(b,dtype=bool)),3)==1)


def test_invalid_exclusion():
    b=np.array([[1.,0.],[np.nan,1.]],dtype='float32')
    a=np.ones((2,2),dtype='float32'); valid=np.ones((2,2),dtype=bool)
    valid[1,1]=False
    score=log_ratio_db(b,a,valid)
    assert (classify_ratio(score)==255).sum()==3


def test_threshold_validation():
    for bad in [0,-1,float('nan'),float('inf')]:
        with pytest.raises(ValueError): classify_ratio(np.ones((2,2)),bad)


def test_shape_validation():
    with pytest.raises(ValueError): log_ratio_db(np.ones((2,2)),np.ones((2,3)),np.ones((2,2)))


def _write_after(root,arr):
    fn=root/'after_VV.tif'
    with rasterio.open(fn,'r+') as d: d.write(arr.astype('float32'),1)


def test_end_to_end_geo_outputs(tmp_path):
    pair=tmp_path/'pair';pair.mkdir();fixture(pair)
    values=np.full((8,8),.23,dtype='float32')
    values[:3,:3]*=2.0
    values[3:5,3:5]*=.5
    _write_after(pair,values)
    out=tmp_path/'out'
    r=run_detection(pair,out,tile_size=3,allow_unverified_registration=True)
    assert r['counts']['increase_pixels']==9
    assert r['counts']['decrease_pixels']==4
    assert r['counts']['unchanged_pixels']==51
    assert r['candidate_change_area_km2']==13*30*30/1e6
    with rasterio.open(out/'change_mask_VV.tif') as ds:
        assert ds.crs.to_epsg()==32636
        assert ds.transform.a==30
        labels=ds.read(1)
        assert labels[0,0]==2 and labels[3,3]==1 and labels[7,7]==0
    assert json.loads((out/'change-summary.json').read_text())['status'].startswith('EXPLORATORY')


def test_no_bypass_no_run(tmp_path):
    pair=tmp_path/'pair';pair.mkdir();fixture(pair)
    with pytest.raises(ValueError,match='subpixel'):
        run_detection(pair,tmp_path/'out')


def test_reject_bad_pair(tmp_path):
    pair=tmp_path/'pair';pair.mkdir();doc=fixture(pair)
    doc['after']['relative_orbit']=99
    (pair/'manifest.json').write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='T02 REJECT'):
        run_detection(pair,tmp_path/'out',allow_unverified_registration=True)


def test_no_input_overwrite(tmp_path):
    pair=tmp_path/'pair';pair.mkdir();fixture(pair)
    with pytest.raises(ValueError,match='separate'):
        run_detection(pair,pair/'outputs',allow_unverified_registration=True)
