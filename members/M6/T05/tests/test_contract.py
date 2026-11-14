from pathlib import Path
import yaml
import pytest
from jsonschema import Draft202012Validator, FormatChecker, validate

ROOT=Path(__file__).resolve().parents[1]
DOC=yaml.safe_load((ROOT/'api-contract.yaml').read_text())

@pytest.mark.contract
def test_openapi_version():
    assert DOC['openapi']=='3.1.0'

@pytest.mark.contract
@pytest.mark.parametrize('endpoint,method',[
    ('/api/v1/runs','post'),('/api/v1/runs/{run_id}','get'),
    ('/api/v1/runs/{run_id}/results','get'),
    ('/api/v1/runs/{run_id}/lineage','get'),
    ('/api/v1/assets/{asset_id}','get'),('/health/ready','get')])
def test_required_routes(endpoint,method):
    assert method in DOC['paths'][endpoint]

@pytest.mark.contract
def test_refs_resolve():
    def visit(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k=='$ref':
                    assert v.startswith('#/')
                    obj=DOC
                    for token in v[2:].split('/'):
                        obj=obj[token.replace('~1','/').replace('~0','~')]
                    assert obj is not None
                else: visit(v)
        elif isinstance(x,list):
            for v in x: visit(v)
    visit(DOC)

@pytest.mark.contract
def test_request_rejects_additional_properties():
    s=DOC['components']['schemas']['CreateRunRequest']
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        Draft202012Validator(s).validate({'scene_before_id':'p1','scene_after_id':'p2','polarization':'VV','method':{'name':'x','version':'1'},'extra':True})

@pytest.mark.contract
def test_public_asset_schema_excludes_storage_uri():
    assert 'storage_uri' not in DOC['components']['schemas']['AssetResponse']['properties']

@pytest.mark.contract
def test_authentication_required_except_readiness():
    assert DOC['security']==[{'bearerAuth':[]}]
    assert DOC['paths']['/health/ready']['get']['security']==[]

@pytest.mark.contract
def test_responses_have_success_and_error():
    for route,verbs in DOC['paths'].items():
        for method,operation in verbs.items():
            if method not in ('get','post','patch','put','delete'): continue
            assert any(int(status)<300 for status in operation['responses'])
            assert any(int(status)>=400 for status in operation['responses'])
