"""T09 software integration tests, using generated test fixtures only."""
import json
from pathlib import Path
import numpy as np
import pytest
import rasterio
from test_t02 import fixture
from pipeline import run_pipeline, binary_candidate_mask, publish_m3


def test_pipeline_real_files_not_claiming_science(tmp_path):
    pair=tmp_path/'pair'; pair.mkdir(); fixture(pair)
    report=run_pipeline(pair,tmp_path/'out',allow_warning=True,tile_size=16)
    assert report['scientific_approval'] is False
    assert report['registration_subpixel_certified'] is False
    assert report['classification_available'] is False
    assert report['delivery_status']=='EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED'
    assert {'score','mask','valid'} <= set(report['artifacts'])
    out=tmp_path/'out'
    for artifact in report['artifacts'].values():
        assert (out/artifact['path']).is_file()
        assert len(artifact['sha256'])==64
    staged=json.loads((out/'staged_filtered_pair'/'manifest.json').read_text())
    assert staged['before']['raster_files']['VV']=='before_VV_filtered.tif'
    assert (out/'T03_filtered'/'filter-report.json').is_file()
    assert (out/'m3-delivery.json').is_file()


def test_reject_unusable_inputs(tmp_path):
    pair=tmp_path/'pair'; pair.mkdir(); fixture(pair)
    doc=json.loads((pair/'manifest.json').read_text());doc['after']['relative_orbit']=77
    (pair/'manifest.json').write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='T02 blocked'):
        run_pipeline(pair,tmp_path/'out',allow_warning=True)
    assert not (tmp_path/'out').exists()


def test_warning_requires_explicit_opt_in(tmp_path):
    pair=tmp_path/'pair';pair.mkdir();fixture(pair)
    with pytest.raises(ValueError,match='T02 blocked'):
        run_pipeline(pair,tmp_path/'out')


def test_no_clobber_and_no_nested_paths(tmp_path):
    pair=tmp_path/'pair';pair.mkdir();fixture(pair)
    with pytest.raises(ValueError,match='overlap'):
        run_pipeline(pair,pair/'output',allow_warning=True)
    out=tmp_path/'out';out.mkdir()
    with pytest.raises(ValueError,match='exists'):
        run_pipeline(pair,out,allow_warning=True)


def test_binary_class_conversion(tmp_path):
    from rasterio.transform import from_origin
    profile=dict(driver='GTiff',width=4,height=1,count=1,dtype='uint8',crs='EPSG:32636',transform=from_origin(1,2,30,30),nodata=255)
    src=tmp_path/'source.tif';dst=tmp_path/'dest.tif'
    with rasterio.open(src,'w',**profile) as d: d.write(np.array([[0,1,2,255]],dtype='uint8'),1)
    binary_candidate_mask(src,dst)
    with rasterio.open(dst) as d:
        assert d.read(1).tolist()==[[0,1,1,255]]
        assert d.crs.to_epsg()==32636


def test_optional_reference_without_provenance_is_exploratory(tmp_path):
    pair=tmp_path/'pair';pair.mkdir();fixture(pair)
    from rasterio.transform import from_origin
    ref=tmp_path/'truth.tif'
    with rasterio.open(ref,'w',driver='GTiff',width=8,height=8,count=1,
                       dtype='uint8',nodata=255,crs='EPSG:32636',transform=from_origin(500000,3500000,30,30)) as d:
        d.write(np.zeros((8,8),dtype='uint8'),1)
    report=run_pipeline(pair,tmp_path/'out',allow_warning=True,tile_size=16,reference=ref)
    assert report['evaluation_available'] is True
    evaluation=json.loads((tmp_path/'out'/'T08_evaluation'/'evaluation-report.json').read_text())
    assert evaluation['status']=='UNVERIFIED_EXPLORATORY'
