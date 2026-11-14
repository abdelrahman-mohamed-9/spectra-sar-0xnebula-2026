"""Export runtime OpenAPI and Pydantic integration contracts (no invented SAR observations)."""
import json
from pathlib import Path
import sys
# Export the integrated application consistently, regardless of invocation cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from spectra.main import create_app
from spectra.domain import schemas

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'contracts'/'generated'
TYPES={
 'm1_sar_scene':schemas.SarSceneCreate,
 'm1_scene_pair':schemas.ScenePairCreate,
 'artifact':schemas.ArtifactCreate,
 'processing_job':schemas.ProcessingJobCreate,
 'm2_change_result':schemas.ChangeResultCreate,
 'm3_impact_assessment':schemas.ImpactAssessmentCreate,
}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'openapi.json').write_text(json.dumps(create_app().openapi(),indent=2,sort_keys=True,default=str)+'\n')
    for name,model in TYPES.items():
        (OUT/f'{name}.schema.json').write_text(json.dumps(model.model_json_schema(),indent=2,sort_keys=True)+'\n')
    print(f'Exported {len(TYPES)} Pydantic schemas and runtime OpenAPI to {OUT}')

if __name__=='__main__':main()
