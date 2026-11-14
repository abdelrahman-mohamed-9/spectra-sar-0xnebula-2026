"""Phase 3.4 offline demo evidence and scientific boundaries."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.build_judge_demo import ROOT, build, inputs, read_original, regions, score_metrics


def test_metrics_match_pinned_holdout_evaluation(tmp_path):
    result=build(output=tmp_path)
    document=json.loads((tmp_path/'mission-data.json').read_text())
    assert result['spatial_ml']['tp']==11316
    assert result['spatial_ml']['fp']==2975
    assert result['baseline']['tp']==24104
    assert result['baseline']['fp']==15450
    assert document['population']['estimate'] is None
    assert document['population']['status']=='UNAVAILABLE'
    assert len(document['zones']['ml'])==25
    assert len(document['zones']['baseline'])==25
    assert document['source']=='https://doi.org/10.5281/zenodo.7946594'
    assert 'file://' not in (tmp_path/'index.html').read_text()
    assert '/*__MISSION_DATA__*/' not in (tmp_path/'index.html').read_text()
    assert '7,745' not in (tmp_path/'index.html').read_text()
    assert '83 residents' not in (tmp_path/'index.html').read_text()


def test_hash_manifest_is_real(tmp_path):
    build(output=tmp_path)
    manifest=json.loads((tmp_path/'evidence-manifest.json').read_text())
    for path,digest in manifest['original_source_files'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    for filename,digest in manifest['derived_demo_files'].items():
        assert hashlib.sha256((tmp_path/filename).read_bytes()).hexdigest()==digest


def test_zone_priority_is_not_based_on_labels():
    arrays,_,transform=read_original(inputs())
    pred=np.where(np.isfinite(arrays['prediction']),arrays['prediction'],255).astype('uint8')
    delta=arrays['after']-arrays['before']
    expected=regions(pred,delta,transform)
    changed_labels=np.where(arrays['labels']==1,0,1)
    # Neither labels nor retrospective metrics are passed to region ranking.
    assert np.count_nonzero(changed_labels==1)>0
    assert regions(pred,delta,transform)==expected
    assert all(z['area_m2']>0 and z['pixels']>=9 for z in expected)


def test_misaligned_inputs_rejected(tmp_path):
    originals=inputs()
    moved={**originals}
    # Validation refuses a raster of the wrong grid, rather than silently warping.
    import rasterio
    import rasterio.transform
    with rasterio.open(originals['before']) as src:
        arr=src.read();profile=src.profile.copy()
    profile['transform']=rasterio.transform.Affine.translation(1,1)*profile['transform']
    dest=tmp_path/'before.tif'
    with rasterio.open(dest,'w',**profile) as ds:ds.write(arr)
    moved['before']=dest
    with pytest.raises(ValueError,match='aligned'):
        read_original(moved)


def test_metrics_ignore_unknown_reference_pixels():
    truth=np.array([[0,1,-1,1]])
    pred=np.array([[0,1,1,0]])
    metrics=score_metrics(truth,pred,np.ones_like(truth,dtype=bool))
    assert (metrics['tp'],metrics['fn'],metrics['tn'],metrics['fp'],metrics['n'])==(1,1,1,0,3)


def test_area_weighted_population_optional_real_source_contract(tmp_path):
    """Software fixture; this population raster is NEVER shipped or described as observed."""
    import rasterio
    from rasterio.transform import from_bounds
    with rasterio.open(inputs()['before']) as ds:
        bounds=ds.bounds
    population=tmp_path/'fixture_population.tif'
    with rasterio.open(population,'w',driver='GTiff',count=1,width=32,height=32,
                       dtype='float32',nodata=-9999,crs='EPSG:4326',
                       transform=from_bounds(*bounds,32,32)) as dst:
        dst.write(np.full((32,32),10,dtype='float32'),1)
    result=build(output=tmp_path/'demo',population_file=population,
                 population_source='Synthetic unit-test-only fixture',population_year=2025)
    payload=json.loads((tmp_path/'demo/mission-data.json').read_text())
    assert result['population']=='AREA_WEIGHTED_MODEL_ESTIMATE'
    assert 540 < payload['population']['estimate'] < 580
    assert 10_000 < payload['population']['study_area_estimate'] < 10_300
    assert payload['population']['provenance']['sha256']==hashlib.sha256(population.read_bytes()).hexdigest()
    assert payload['zones']['ml'][0]['population_by_radius']['0']['estimated_residents'] is not None
    # The buffer crosses beyond supplied coverage; do not reinterpret absent data as zero.
    assert payload['zones']['ml'][0]['population_by_radius']['300']['estimated_residents'] is None
