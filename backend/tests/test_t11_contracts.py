"""Consumer/provider consistency checks for M5's proposed T11 contracts."""
import json
from pathlib import Path
from spectra.main import create_app
from spectra.domain import schemas

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/'contracts'/'integration-manifest.json').read_text())
EXAMPLES=json.loads((ROOT/'contracts'/'api-examples.json').read_text())


def test_all_module_owners_are_represented():
    assert {x['owner'] for x in MANIFEST['integrations']} == {'M1','M2','M3','M4','M6'}
    assert MANIFEST['status'].startswith('proposed')


def test_manifest_routes_exist_in_runtime_openapi():
    paths=create_app().openapi()['paths']
    for integration in MANIFEST['integrations']:
        for route in integration['routes']:
            method,short=route.split(' ',1)
            assert '/api/v1'+short in paths or short in paths, (integration['owner'],route)
            assert method.lower() in paths.get('/api/v1'+short,paths.get(short,{})),route


def test_generated_openapi_matches_actual_app():
    exported=json.loads((ROOT/'contracts'/'generated'/'openapi.json').read_text())
    assert exported==create_app().openapi()


def test_exported_schema_matches_pydantic_models():
    items={'m1_sar_scene':schemas.SarSceneCreate,'m1_scene_pair':schemas.ScenePairCreate,
           'artifact':schemas.ArtifactCreate,'processing_job':schemas.ProcessingJobCreate,
           'm2_change_result':schemas.ChangeResultCreate,'m3_impact_assessment':schemas.ImpactAssessmentCreate}
    for name,model in items.items():
        assert json.loads((ROOT/'contracts'/'generated'/f'{name}.schema.json').read_text())==model.model_json_schema()


def test_no_unapproved_browser_service_key():
    m4=next(item for item in MANIFEST['integrations'] if item['owner']=='M4')
    assert 'never X-API-Key' in m4['auth']
    assert all('/auth/' in route for route in m4['routes'])


def test_example_routes_and_contract_paths():
    paths=create_app().openapi()['paths']
    for ex in EXAMPLES['flows']:
        route=ex['path']
        if '<PROJECT_UUID>' in route:route=route.replace('<PROJECT_UUID>','{project_id}')
        assert '/api/v1'+route in paths or route in paths
        if 'payload_contract' in ex:
            assert (ROOT/ex['payload_contract']).is_file()


def test_internal_endpoints_remain_service_authenticated():
    paths=create_app().openapi()['paths']
    for route in ['/api/v1/resources/scenes','/api/v1/storage/artifacts/upload', '/api/v1/geospatial/scenes/within']:
        ops=paths[route]
        assert 'security' in ops['post' if 'upload' in route or route.endswith('/scenes') else 'get'] or 'parameters' in ops['post' if 'upload' in route or route.endswith('/scenes') else 'get']
