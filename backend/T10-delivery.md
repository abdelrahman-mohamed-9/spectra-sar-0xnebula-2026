# T10 — Authentication & API Security

## Implementation
- PostgreSQL migration `0002_auth_rbac` introduces `users` and `project_memberships`.
- Argon2id password hashes. Login verifies user status and password without disclosing whether email exists.
- Short-lived (15 minute default) signed HS256 access JWT with `iss`, `aud`, `sub`, `jti`, `iat`, `nbf`, `exp`; only explicit HS256 accepted.
- `viewer < analyst < editor < owner`; platform admins bypass per-project checks (grant separately through carefully controlled administrative operations).
- User routes `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `GET /api/v1/auth/projects/{project_id}/access`, `GET /api/v1/auth/projects/{project_id}/artifacts`, `GET /api/v1/auth/projects/{project_id}/jobs`.
- Default-deny: missing membership returns 404; insufficient role returns 403. Project resource queries are project-filtered *after* authorization.
- Provision an initial account through `scripts/create_user.py` with an interactive password prompt; no public signup and no default credentials.

## Run
1. Set `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `INTERNAL_API_KEY`, `JWT_SECRET` to strong independent values in `deploy/.env` (at least 32 chars for latter two). Never commit secrets.
2. `cd deploy && docker compose up --build -d` (migrate service runs `alembic upgrade head`).
3. Create user: `docker compose exec api python scripts/create_user.py --email analyst@example.org --project-id <existing-uuid> --role analyst` (script is included in container build context).
4. `POST /api/v1/auth/login` with `{"email":"analyst@example.org","password":"your-password"}`; send returned token as `Authorization: Bearer <token>` to new user routes.
5. Test `GET /api/v1/auth/me` and project access with correct and incorrect project UUIDs.

## Security boundaries / unfinished work
**CRITICAL**: Existing T06–T09 `/resources`, `/geospatial`, `/processing-jobs`, `/storage` endpoints still use a shared **service API key** and remain internal worker-to-worker routes. T10 does NOT retrofit them with JWT/user RBAC. Do not expose them publicly or embed INTERNAL_API_KEY in browsers. Place these endpoints behind a private network/API gateway; add project RBAC to every user-facing CRUD/dispatch/upload/download endpoint before production.

No account lockout or rate limiter, refresh-token rotation, token revocation, identity recovery, 2FA, central audit logging, or real Docker/PostgreSQL integration test yet. Use an edge rate limiter and TLS. User deletion/deactivation invalidates API tokens on next request by checking active status; otherwise JWTs last up to 15 minutes. Production service identity should replace the shared internal key. `POST /auth/login` may be abused without rate limiting; ensure gateway protection before public deployment.

## Verification
`PYTHONPATH=src pytest -q` — 116 tests passed locally (includes preceding 109). This uses mocked database interactions; no real PostgreSQL/Redis/MinIO authentication integration was tested.
