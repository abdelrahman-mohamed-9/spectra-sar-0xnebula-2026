# T08 — Processing Job Management

## Implemented

- `src/spectra/workers/job_manager.py`: database-authoritative atomic queued→running claims, running→terminal transitions, transient requeue, queued-only cancellation, persisted status lookups.
- `src/spectra/workers/task_queue.py`: Celery/Redis broker, configurable retries of explicitly transient failures, strict allowlist of registered scientific processors, no fake SAR output.
- `src/spectra/api/v1/jobs.py`: authenticated GET status / POST dispatch / POST cancel.
- `deploy/compose.yaml`: dedicated Celery worker with migrated PostGIS and healthy Redis dependencies.
- `tests/test_t08.py`: race-protection SQL-contract tests, authentication, dispatch, broker-failure, status and cancellation tests.

## Run (Docker required)

From `backend/deploy`, create `.env` from `.env.example`, set strong credentials, then:

```sh
docker compose up --build -d
docker compose logs --tail=100 worker
docker compose exec worker celery -A spectra.workers.task_queue:celery_app inspect ping
```

Create a job with the existing `POST /api/v1/resources/jobs` endpoint using an **existing** `project_id` and `scene_pair_id` from real imported data. Then POST `/api/v1/processing-jobs/{job_id}/dispatch` with the service API key. Check GET `/api/v1/processing-jobs/{job_id}`.

**Important:** Until real M1/M2/M3 processing functions are integrated and registered, dispatched jobs deliberately fail with a handler-not-configured reason; successful results are never invented.

## Known operational work remaining

1. Verify against real PostgreSQL/PostGIS and Redis and test actual Celery worker delivery. Celery could not be installed in the current offline test environment.
2. Delivery is **at-least-once**: a worker crash after acquiring the DB claim can leave `running` state stuck. Add a lease/heartbeat/reaper with explicit idempotency guarantees before production.
3. Dispatch uses DB row creation followed by broker send; a crash between the two can lose an enqueue. Add a transactional outbox and a dispatcher to close this gap.
4. The same job may be dispatched twice while queued; only one worker can claim it, but duplicate broker messages are possible.
5. No live progress percentage, distributed tracing, worker secrets rotation, end-user RBAC or hard job cancellation yet.
6. Never retry scientific data-invalid failures: only `TransientProcessingError` is retryable.
7. Worker execution must register concrete real processors on import/startup, and persist final artifact references transactionally with results.

## Acceptance

All local tests pass; live queue/DB infrastructure validation remains outstanding.
