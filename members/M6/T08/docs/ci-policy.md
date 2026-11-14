# CI Quality Gates — policy v1

| Gate | Enforcement | Owner |
|---|---|---|
| All task test folders present (T02–T07) | Required | M6 |
| Python unit + contract + scientific-metric tests | Required (offline) | M6 + module owner |
| Workflow structure & read-only permissions | Required | M6 |
| Live API integration | Deferred (no M4 endpoint provided) | M4/M6 |
| PostgreSQL migrations | Deferred (no DB provisioned in CI) | M4/M6 |
| S3/MinIO & SAR acquisition | Deferred | M1/M6 |
| Scientific quality on real labels | Deferred | M2/M3/M6 |
| Production deployment | Out of Phase 1 scope | M4/M6 |

## Security and release controls

- No secrets or `.env` in repository; environment values belong in GitHub Secrets if live jobs are later added.
- Workflow uses `contents: read`, `persist-credentials: false` and no PR-origin shell interpolation.
- Avoid granting pull requests access to privileged deployment tokens.
- Protect `main`, require PR reviews and named CI check.
- Do not mark T08 operationally complete until one successful GitHub Actions run is verified.
- For stronger supply-chain controls before deployment: pin actions to immutable commits, add dependency review and provenance attestation.
