import pytest
from src.qa_validators import validate_pair, QualityError

# Synthetic METADATA ONLY for deterministic unit tests; not simulated SAR images,
# not scientific observations or validation of remote sensing performance.
@pytest.fixture
def pair():
    before={'provider':'example-provider','provider_scene_id':'unit-scene-a',
        'acquired_at':'2026-01-01T00:00:00Z','orbit_direction':'ASCENDING',
        'polarizations':['VV','VH'],'incidence_angle_degrees':34.0}
    after={**before,'provider_scene_id':'unit-scene-b','acquired_at':'2026-01-13T00:00:00Z',
        'incidence_angle_degrees':34.8}
    return before,after

@pytest.mark.scientific
def test_compatible_metadata(pair): assert validate_pair(*pair)

@pytest.mark.scientific
@pytest.mark.parametrize('field,value',[
    ('orbit_direction','DESCENDING'),('polarizations',['HH']),
    ('incidence_angle_degrees',37.0),('provider_scene_id','unit-scene-a'),
    ('acquired_at','2025-12-31T00:00:00Z'),('acquired_at','invalid')])
def test_reject_incompatible(pair,field,value):
    a,b=pair; b[field]=value
    with pytest.raises(QualityError): validate_pair(a,b)

@pytest.mark.scientific
def test_naive_timestamps_rejected(pair):
    a,b=pair; b['acquired_at']='2026-01-13T00:00:00'
    with pytest.raises(QualityError,match='timezone'):validate_pair(a,b)

@pytest.mark.scientific
def test_missing_metadata_rejected(pair):
    a,b=pair; del b['provider']
    with pytest.raises(QualityError,match='missing'):validate_pair(a,b)
