# SPECTRA-SAR — Member 6 / Phase 1 / T09: Technical Documentation

**Version:** 0.1 (integration proposal) | **Owner:** M6 | **Date:** 2026-11-13

This is the documentation package for the existing M6 T01–T08 deliverables. It does **not** mean that the M1–M5 services have been built or that an end-to-end Sentinel-1 processing pipeline has been run. Start with [docs/setup-guide.md](docs/setup-guide.md).

## Documentation index

| Document | Use |
|---|---|
| [setup-guide.md](docs/setup-guide.md) | Prerequisites, ZIP assembly, local environment, database, offline tests |
| [architecture.md](docs/architecture.md) | Responsibility map, data boundaries and proposed system architecture |
| [integration-guide.md](docs/integration-guide.md) | M1–M6 handoff protocol, evidence and acceptance |
| [api-guide.md](docs/api-guide.md) | Proposed T04 API routes, authentication expectations and limitations |
| [data-and-science.md](docs/data-and-science.md) | Real SAR provenance, alignment, validation and scientific claims |
| [testing-and-ci.md](docs/testing-and-ci.md) | Test matrix, local/remote CI and acceptance criteria |
| [troubleshooting.md](docs/troubleshooting.md) | Common failures and practical diagnostics |
| [release-checklist.md](docs/release-checklist.md) | T09 sign-off and remaining deployment blockers |
| [../scripts/check_docs.py](scripts/check_docs.py) | Offline links/files validation for this documentation package |

## What is implemented as of T09
- T02: Python setup helpers and a local Docker Compose proposal for PostgreSQL + MinIO.
- T03: SQL schema + Python DB helper and migration scripts; requires a live database to verify.
- T04: OpenAPI 3.1 **contract**, not a running HTTP service.
- T05: automated offline tests plus opt-in live integration checks.
- T06: local-file SHA-256 + provenance manifest tools; no authenticated MinIO/S3 verification yet.
- T07: evaluation utilities for aligned prediction/ground-truth numpy arrays; no model or measured accuracy yet.
- T08: CI workflow template; remotely executing GitHub Actions and CD are not established.

## Scope decisions to resolve
M4 must approve the API/database model and auth model. M1 must provide genuine provider IDs, imagery and spatial alignment evidence. M2 must provide actual prediction rasters; M3 independent reference labels. M5 consumes only approved M4 APIs. M6 validates integration and reproducibility.

**Security:** Never commit `.env`, secret tokens, provider credentials, large raw data, or real user identifiers. T02 credentials are for local development; do not expose MinIO root keys to clients.
