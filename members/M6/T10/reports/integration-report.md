# M6 Phase 1 — T10 Integration Validation Report

Generated (UTC): 2026-11-13T16:43:30.826273+00:00
Overall: **BLOCKED**

| Check | Status | Evidence / finding |
|---|---|---|
| `package.T01` | PASS | Required entrypoints found — ../T01 |
| `package.T02` | PASS | Required entrypoints found — ../T02 |
| `package.T03` | PASS | Required entrypoints found — ../T03 |
| `package.T04` | PASS | Required entrypoints found — ../T04 |
| `package.T05` | PASS | Required entrypoints found — ../T05 |
| `package.T06` | PASS | Required entrypoints found — ../T06 |
| `package.T07` | PASS | Required entrypoints found — ../T07 |
| `package.T08` | PASS | Required entrypoints found — ../T08 |
| `package.T09` | PASS | Required entrypoints found — ../T09 |
| `live.backend` | BLOCKED | Backend URL not supplied |
| `live.database` | BLOCKED | DATABASE_URL not supplied |
| `e2e.M1` | BLOCKED | No team evidence manifest supplied |
| `e2e.M2` | BLOCKED | No team evidence manifest supplied |
| `e2e.M3` | BLOCKED | No team evidence manifest supplied |
| `e2e.M4` | BLOCKED | No team evidence manifest supplied |
| `e2e.M5` | BLOCKED | No team evidence manifest supplied |
| `e2e.real_sar` | BLOCKED | No verified Sentinel-1 processing evidence supplied |
| `e2e.scientific` | BLOCKED | No independent reference evaluation evidence supplied |
| `e2e.github` | BLOCKED | No GitHub-hosted workflow evidence supplied |

**Interpretation:** Evidence SHA matches establish file integrity only; reviewers must verify independent scientific data, real SAR scene IDs, and true end-to-end execution.
