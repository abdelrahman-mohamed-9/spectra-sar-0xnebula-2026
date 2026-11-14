# Phase 1 final acceptance checklist — M6

- [ ] T01–T09 directories and contract documents present and reviewer-approved
- [ ] Docker PostgreSQL and MinIO real health checks passed
- [ ] Database migrations applied to target deployment, verified without modifying production data
- [ ] Backend `GET /health/ready` returns 200 and valid readiness object
- [ ] M4 implements all T04 API paths, security/ownership, error behavior and idempotency
- [ ] One **real provider-verified Sentinel-1 scene pair** with matching AOI/orbit/polarization and traceable scene IDs
- [ ] M1 calibrated/registered raster artifacts and checksums verified
- [ ] M2 produces real change mask and uncertainty details, not a generated demonstration
- [ ] M3 impact calculations explicitly cite their population/infrastructure source and uncertainty
- [ ] Independent (not training) reference labels align spatially with outputs; T07 metrics computed and reviewed
- [ ] M5 renders authenticated run status, authorized map products and appropriate uncertainty messaging
- [ ] M6 lineage verifies input-to-output relations and matching file hashes across storage
- [ ] GitHub Actions run succeeded on hosted GitHub; branch protection status checks active
- [ ] Integration tests exercised a real run from request -> processing -> stored outputs -> UI
- [ ] Security tests: unauthorized access denied, no credentials in logs/reports, least privilege storage
- [ ] M1/M2/M3/M4/M5/M6 sign off, with Git revision and test commands recorded

**Gate policy:** Phase 1 MUST remain OPEN if any required check is pending, blocked or failed. Reviewers should evaluate actual report contents, not only evidence hashes.
