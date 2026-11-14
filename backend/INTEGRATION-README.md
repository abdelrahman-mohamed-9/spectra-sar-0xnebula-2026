# M5 in the unified Phase 1 release

Use the root `README-START-HERE.md` and root `compose.yaml`.

The backend is the original M5 implementation extended with `phase1.api` and an explicit Celery Phase 1 handler. Canonical scientific source lives at `../members/M2` and `../members/M3/T09`; obsolete embedded copies were removed. `scripts/spectra_integrate.py` retains lower-level handoff/publication commands and now supports the explicit NISAR HHHH contract.

`/health/live` is process liveness. `/health/ready` requires successful protocol checks of all configured infrastructure. Local run-file API mode is independently usable even when distributed infrastructure is absent.

Current delivery validation and remaining real-data/infrastructure blockers are recorded at `../reports/VALIDATION.md`.
