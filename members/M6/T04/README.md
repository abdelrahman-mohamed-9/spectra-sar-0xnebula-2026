# SPECTRA-SAR — M6 / Phase 1 / T04

Deliverables: `api-contract.yaml` (OpenAPI 3.1) + `integration-plan.md` (ownership, DB mapping, implementation sequence, acceptance criteria).

## Test

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```

For additional OpenAPI semantic validation (requires installing an optional third-party package):

```bash
python3 -m pip install openapi-spec-validator
python3 -c "from openapi_spec_validator import validate; import yaml; validate(yaml.safe_load(open('api-contract.yaml'))); print('OpenAPI semantic validation passed')"
```

No external services, real imagery or backend are bundled; this is a specification intended for M4 implementation and M5 integration. Tests check parsing, endpoint coverage, references and selected invariants, **not live functionality**. See `integration-plan.md` for documented gaps.
