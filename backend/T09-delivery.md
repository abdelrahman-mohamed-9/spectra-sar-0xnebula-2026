# T09 — Storage & File Management

## Delivered
- `storage/file_validator.py`: extension allowlist, magic-byte validation and filename safety.
- `storage/storage_service.py`: bounded stream to temp file, SHA-256, opaque S3 keys, private upload, 5-minute signed download.
- `api/v1/storage.py`: authenticated upload/presigned access and artifact DB registration with compensating deletion on transaction failures.
- Updated Docker Compose with bucket-init job, fixed malformed T08 compose file, Redis persistence and dependencies.

## Integration
- Requests originate from trusted services carrying `X-API-Key` (>=32 configured characters).
- Upload `multipart/form-data` with `project_id`, `kind`, optional `scene_id`, `file`.
- GET `/api/v1/storage/artifacts/{uuid}/download-url` returns a short-lived link; backend looks up artifact ID, never accepts arbitrary S3 URI.
- Supported: `.tif`, `.tiff`, `.png`, `.json`, `.geojson`, `.zip` (not arbitrary `.SAFE` folders). ZIP files are stored, **not extracted**.
- Object SHA-256 is calculated over actual input bytes; remote S3 existence is not a scientific verification.
- 512 MiB default upload limit, configurable via `MAX_UPLOAD_BYTES` (1–5 GiB). Uploads are spooled to a temporary file; reverse proxy should enforce body-size limits too.
- Object storage is private. For remote clients, generated MinIO presigned links with `http://minio:9000` hostname will not resolve; configure public access hostname in production or serve through an authenticated gateway.
- Minimal API key is service-level, NOT project RBAC or user authorization. Do not expose these endpoints to untrusted browsers; T10 adds security.
- Storage and relational commit are not atomic; failures try best-effort object cleanup. Reconcile orphan objects as a future maintenance task.

## Quick verification
```bash
cd backend
python -m pytest -q
cd deploy
cp .env.example .env
# Set all secrets; use 32+ chars for INTERNAL_API_KEY
# docker compose config && docker compose up --build -d
```

## Outstanding checks
- Live S3/MinIO, PostgreSQL and Docker integration is NOT certified by unit tests.
- Exact image georeferencing, scientific provenance and archive content scanning are the remit of M1/M2 and later security phases.
- S3 object immutability, encryption, quotas, retention and audit logging require production hardening.
