import json
import numpy as np
import rasterio
from rasterio.transform import from_origin
import pytest
from filters import masked_lee, process_pair


def test_constant_scene_stays_constant():
    arr=np.ones((33,33),dtype='float32')*0.2
    result=masked_lee(arr,np.ones_like(arr,dtype=bool),window=7,looks=4)
    assert np.allclose(result,arr,rtol=1e-5)


def test_masks_not_contaminate_neighborhood():
    arr=np.full((25,25),0.4,dtype='float32'); arr[12,12]=1e8
    valid=np.ones_like(arr,dtype=bool);valid[12,12]=False
    result=masked_lee(arr,valid)
    assert np.isnan(result[12,12]);assert np.isclose(result[12,13],0.4,atol=1e-5)


def test_speckle_variance_reduced():
    rng=np.random.default_rng(10)
    arr=rng.gamma(shape=4,scale=0.25,size=(160,160)).astype('float32')
    den=masked_lee(arr,np.ones_like(arr,dtype=bool),looks=4)
    assert np.var(den[12:-12,12:-12]) < np.var(arr[12:-12,12:-12])*0.5


def test_retain_step_boundary():
    rng=np.random.default_rng(4)
    arr=np.ones((100,100),dtype='float32');arr[:,50:]=4
    arr*=rng.gamma(8,1/8,arr.shape).astype('float32')
    den=masked_lee(arr,np.ones_like(arr,dtype=bool),looks=8)
    assert float(np.mean(den[15:85,10:30])) < 1.4
    assert float(np.mean(den[15:85,70:90])) > 3.4


def test_invalid_parameters():
    x=np.ones((7,7),dtype='float32')
    with pytest.raises(ValueError):masked_lee(x,x>0,window=4)
    with pytest.raises(ValueError):masked_lee(x,x>0,looks=0)


def _create_pair(root):
    root.mkdir(parents=True)
    rng=np.random.default_rng(42)
    profile=dict(driver='GTiff',height=45,width=51,count=1,dtype='float32',crs='EPSG:32633',transform=from_origin(500000,4500000,30,30))
    for side in ('before','after'):
        vals=rng.gamma(4,.03,(45,51)).astype('float32')
        with rasterio.open(root/f'{side}_VV.tif','w',**profile) as dst:dst.write(vals,1)
        with rasterio.open(root/f'{side}_valid_mask.tif','w',**{**profile,'dtype':'uint8'}) as dst:dst.write(np.ones((45,51),dtype='uint8'),1)
    doc={'schema_version':'1.0','pair_id':'QA_SYNTHETIC_PAIR','source_provider':'QA_SYNTHETIC_NOT_REAL',
         'processing_software':'QA_GENERATOR','processing_version':'0.1','product_type':'RTC',
         'acquisition_mode':'IW','radiometry':'gamma0_terrain','units':'linear_power','polarizations':['VV'],
         'grid':{'crs':'EPSG:32633','pixel_size_m':30,'width':51,'height':45}}
    for side,day in [('before','01'),('after','13')]:
        doc[side]={'scene_id':f'QA_{side}', 'acquired_utc':f'2026-01-{day}T00:00:00Z',
                   'relative_orbit':23,'orbit_direction':'ASCENDING','incidence_angle_deg_summary':35.,
                   'raster_files':{'VV':f'{side}_VV.tif'},'valid_mask_file':f'{side}_valid_mask.tif'}
    (root/'manifest.json').write_text(json.dumps(doc))
    return root


def test_end_to_end_no_tile_seams(tmp_path):
    pair=_create_pair(tmp_path/'input');output=tmp_path/'out'
    result=process_pair(pair,output,tile=13,window=7,allow_warning=True)
    assert result['images']['before']['valid_pixels']==45*51
    with rasterio.open(pair/'before_VV.tif') as src, rasterio.open(output/'before_VV_lee.tif') as dst:
        inp=src.read(1); got=dst.read(1)
        reference=masked_lee(inp,np.ones_like(inp,dtype=bool),window=7)
        assert np.allclose(got,reference,rtol=1e-5,atol=1e-6)
        assert dst.transform==src.transform
        assert dst.crs==src.crs


def test_input_not_modified(tmp_path):
    pair=_create_pair(tmp_path/'input');output=tmp_path/'out'
    original=(pair/'before_VV.tif').read_bytes()
    process_pair(pair,output,tile=16,allow_warning=True)
    assert (pair/'before_VV.tif').read_bytes()==original


def test_output_directory_protected(tmp_path):
    pair=_create_pair(tmp_path/'pair')
    with pytest.raises(ValueError):process_pair(pair,pair/'out')
