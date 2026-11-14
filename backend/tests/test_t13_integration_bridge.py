"""Integration boundary checks. Generated arrays are TEST FIXTURES, never observation data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/spectra_integrate.py'
CONVERT=Path(__file__).resolve().parents[1]/'scripts/m2_mask_to_m3_geojson.py'
spec=importlib.util.spec_from_file_location('integration_cli',SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_no_real_m2_delivery_fails(tmp_path):
    with pytest.raises(ValueError,match='not found'):
        module.verified_m2(tmp_path/'missing.json')


def make_fixture(tmp_path):
    raw=tmp_path/'T05_change'
    raw.mkdir(parents=True)
    mask=raw/'change_mask_VV.tif'
    data=np.array([[0,1,2],[255,1,0],[0,0,2]],dtype='uint8')
    with rasterio.open(mask,'w',driver='GTiff',height=3,width=3,count=1,dtype='uint8',
                       crs='EPSG:4326',transform=from_origin(30,15,0.001,0.001),nodata=255) as r:
        r.write(data,1)
    doc={'schema_version':'1.0','producer':'SPECTRA-SAR-M2-T09',
         'pair_id':'test-only-not-observation','polarization':'VV',
         'scientific_approval':False,'delivery_status':'EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED',
         'artifacts':{'change_mask':{'path':'T05_change/change_mask_VV.tif',
              'sha256':module.digest(mask)}},'limitations':['fixture only']}
    manifest=tmp_path/'m3-delivery.json'
    manifest.write_text(json.dumps(doc))
    return manifest,mask


def test_real_file_verification_and_checksum_fail_closed(tmp_path):
    manifest,mask=make_fixture(tmp_path)
    result,path=module.verified_m2(manifest)
    assert path==mask and result['scientific_approval'] is False
    with mask.open('ab') as f:f.write(b'altered')
    with pytest.raises(ValueError,match='Checksum mismatch'):
        module.verified_m2(manifest)


def test_four_class_mask_converts_without_inventing_hazard(tmp_path):
    manifest,mask=make_fixture(tmp_path)
    output=tmp_path/'candidate.geojson'
    subprocess.run([sys.executable,str(CONVERT),'--mask',str(mask),'--out',str(output)],check=True,capture_output=True)
    result=json.loads(output.read_text())
    assert result['type']=='FeatureCollection'
    assert {f['properties']['change_class'] for f in result['features']}=={1,2}
    assert all(f['properties']['evidence_status']=='UNVERIFIED' for f in result['features'])
    assert all(f['geometry']['type'] in ('Polygon','MultiPolygon') for f in result['features'])


def test_prepare_m3_and_protect_source_evidence(tmp_path):
    manifest,mask=make_fixture(tmp_path/'m2')
    class Args:pass
    args=Args();args.m2_delivery=manifest;args.out=tmp_path/'bridge'
    module.prepare(args)
    proof=module.verified_bridge(args.out/'bridge-manifest.json')
    assert proof['scientific_approval'] is False
    output=args.out/'candidate_change_footprint.geojson'
    output.write_text('{}')
    with pytest.raises(ValueError,match='modified'):
        module.verified_bridge(args.out/'bridge-manifest.json')


def test_no_publish_without_credentials_or_valid_id(tmp_path,monkeypatch):
    class Args:api_url='http://127.0.0.1:8000'
    monkeypatch.delenv('SPECTRA_INTERNAL_API_KEY',raising=False)
    with pytest.raises(ValueError,match='SPECTRA_INTERNAL_API_KEY'):
        module.backend_client(Args())
    with pytest.raises(ValueError):module.uuid('not-a-uuid')
    class Insecure:api_url='http://example.com:8000'
    with pytest.raises(ValueError,match='HTTPS'):
        module.backend_client(Insecure())
