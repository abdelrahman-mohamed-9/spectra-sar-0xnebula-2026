"""Synthetic displacement fixtures test math only, not real glacier accuracy."""
import io
import json
import zipfile
import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from phase2.glacier import analyze_bundle


def bundle(snr=10, units='meters'):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr('manifest.json',json.dumps({'source_product':'SYNTHETIC_TEST_ONLY',
            'source_url':'https://example.org/test','glacier_source':'synthetic mask',
            'reference_time':'2026-10-17T00:00:00Z','secondary_time':'2026-10-29T00:00:00Z',
            'units':units,'offset_convention':'secondary_minus_reference'}))
        for name,value in [('along_track',24),('slant_range',-12),('snr',snr),('glacier_mask',1)]:
            with MemoryFile() as memory:
                with memory.open(driver='GTiff',height=5,width=5,count=1,dtype='float32',
                    crs='EPSG:4326',transform=from_origin(-153.12,64.65,.001,.001),nodata=-9999) as raster:
                    raster.write(np.full((5,5),value,dtype='float32'),1)
                archive.writestr(name+'.tif',memory.read())
    return stream.getvalue()


AOI=[-153.134,64.6236,-153.0562,64.6564]


def test_signed_components_and_quality_rejection():
    result=analyze_bundle(bundle(),AOI)
    assert result['elapsed_days']==12
    assert result['retained_cells']==25
    assert result['components']['along_track']['median_rate_m_per_day']==2
    assert result['components']['slant_range']['median_rate_m_per_day']==-1
    assert len(result['file_hashes'])==5
    rejected=analyze_bundle(bundle(snr=1),AOI)
    assert rejected['status']=='NO_VALID_MEASUREMENTS'
    assert rejected['components']['along_track']['median_rate_m_per_day'] is None


def test_wrong_area_units_and_zip_rejected():
    with pytest.raises(ValueError,match='overlap'):
        analyze_bundle(bundle(),[10,20,11,21])
    with pytest.raises(ValueError,match='meters'):
        analyze_bundle(bundle(units='pixels'),AOI)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr('../bad','bad')
    with pytest.raises(ValueError,match='exactly'):
        analyze_bundle(stream.getvalue(),AOI)


def test_glacier_api_owner_persistence_and_tamper(tmp_path):
    from phase2.jobs import Jobs,work_one
    from tests_phase2.test_system import app_for
    from fastapi.testclient import TestClient
    queue=Jobs(tmp_path/'state')
    job=queue.submit('A','nisar-oct2026','conservative')
    work_one(queue)
    route='/api/v1/phase2/jobs/'+job+'/glacier'
    with TestClient(app_for(queue)) as client:
        assert client.post(route,content=bundle()).status_code==401
        assert client.post(route,content=bundle(),headers={'X-Test-Actor':'B'}).status_code==404
        response=client.post(route,content=bundle(),headers={'X-Test-Actor':'A'})
        assert response.status_code==200, response.text
        result=response.json()
        assert client.post(route,content=b'bad',headers={'X-Test-Actor':'A'}).status_code==422
    with TestClient(app_for(Jobs(queue.root))) as client:
        assert client.get(route,headers={'X-Test-Actor':'A'}).json()[0]==result
        assert client.get(route,headers={'X-Test-Actor':'B'}).status_code==404
        (queue.runs/job/'glacier-supplements'/result['id']/'source.zip').write_bytes(b'tampered')
        assert client.get(route,headers={'X-Test-Actor':'A'}).status_code==409
