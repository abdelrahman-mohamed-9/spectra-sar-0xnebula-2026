# T04 proposed HTTP API: integration guide

The source of truth for **proposed** API definitions is `T04/api-contract.yaml`, OpenAPI 3.1, version 0.1.0. M4 must implement and confirm endpoints; T04 unit tests do **not** prove a running backend.

| Method | Route | Purpose |
|---|---|---|
| GET | `/health/ready` | M4 readiness, when implemented |
| POST | `/api/v1/runs` | create analysis run |
| GET | `/api/v1/runs/{run_id}` | poll run status |
| GET | `/api/v1/runs/{run_id}/results` | get analysis result records |
| GET | `/api/v1/runs/{run_id}/lineage` | get provenance associations |
| GET | `/api/v1/assets/{asset_id}` | M4-authorized asset access |

## Caller responsibilities
- Backend base URL is a deploy-time configuration variable, e.g. `SPECTRA_API_BASE_URL=http://127.0.0.1:8000` **only if M4 runs it there**.
- Follow T04 schemas and documented response codes; do not infer JSON shape from this summary. Use UUIDs and any documented required data exactly as T04 specifies.
- Apply bearer authentication/authorization as approved by M4. **Never** put database passwords or MinIO root secrets into browser JS.
- Use strict input validation and explicit request/run correlation IDs. Do not assume completed status implies scientific acceptance.
- Assets should be streamed or returned through scoped, short-lived authorized URLs; the contract must be reviewed before public access.

## Practical test when M4 launches API
```bash
# Only if an actual M4 service is listening at this address
curl -i http://127.0.0.1:8000/health/ready
# Then run opted-in T05 integration tests per its README,
# with valid credentials and real DB service configured.
```

## Outstanding design decisions
- M4 approval of DB/schema mapping, data provenance fields, status lifecycle, error codes and auth model.
- Disambiguation of provider scene/product IDs across catalogs/sources.
- Pagination, job timeout/cancellation, audit event policy, asset access mechanism.
- Compatibility of result confidence metrics and provenance links with actual M2/M3 outputs.
