# Service boundaries and pending decisions

This is a development scaffold proposed by M6, not an adopted architecture.

| Member | Owns | M6 responsibility |
|---|---|---|
| M1 | Real SAR data source and processing | verify artifact handoff and metadata contract |
| M2 | SAR filtering, AI and change detection | validate result schema and artifact lineage |
| M3 | Geospatial impact and decision intelligence | validate impact payloads and semantics |
| M4 | Backend API, schema and application database access | agree DB choice, connection settings, migrations, API contract |
| M5 | Frontend UI | agree backend origin/auth and runtime setup |
| M6 | Environment, integration checks, QA | keep infrastructure repeatable, avoid rewriting member sources |

## Decisions before production or shared deployment
1. M4 approves PostgreSQL and owns schema migrations. No business tables are provisioned in T02.
2. Team approves S3-compatible storage vs another artifact store and bucket naming.
3. Choose service implementation and deployment network boundaries before adding member containers.
4. Use secrets manager, limited-purpose non-root credentials, TLS, access controls, backup/restore and version pinning/digest review for non-local deployments.
5. Approve T01 contracts before claiming interface integration is complete.
6. Validate container image availability on target system and review image versions/security advisories.

### Safety
Default service ports bind to 127.0.0.1 only. Do not expose MinIO admin or Postgres on public networks. MinIO root credentials are for local development; use scoped application accounts in real deployments. Local data volumes are persistent and `down --volumes` deletes them.
