# T09 documentation acceptance checklist

## Documentation (T09)
- [x] M6 T01–T08 package structure reviewed from available archives
- [x] Setup procedure and normalization procedure documented
- [x] System architecture and responsibility boundaries documented
- [x] T04 proposed API paths and ownership documented
- [x] Reproducible QA/CI commands and limits documented
- [x] Troubleshooting and scientific validity caveats documented
- [ ] Team reviewers (M1–M5, especially M4) confirm accuracy and sign off

## Live system gates (not completed by authoring T09)
- [ ] Docker Compose started on target machine and health checks recorded
- [ ] Proposed T03 migration applied and approved by M4
- [ ] MinIO bucket configured, objects stored and authenticated hashes verified
- [ ] M4 backend actually implements and secures the API
- [ ] One real verified Sentinel-1 scene pair processed M1→M2→M3
- [ ] Independent validation dataset and T07 scientific report recorded
- [ ] M5 displays authorized real results and errors
- [ ] GitHub-hosted T08 workflow executes and required status check enforced
- [ ] Cross-component end-to-end test results published for T10

## Sign-off record template
| Field | Value |
|---|---|
| Revision / Git SHA | PENDING |
| Reviewers | PENDING |
| Date | PENDING |
| Test commands and exact results | PENDING |
| Verified provider scene IDs | PENDING |
| Known remaining risks | See unchecked live system gates |
