# SPECTRA-SAR — M1 Phase 1 | Consolidated Handoff

**Owner:** Member 1 — SAR Data Engineering

**Case:** Mendenhall Valley flood + Mendenhall Glacier motion, Juneau, Alaska, USA.

## Open these first
1. `STATUS.json` — factual task status. No real SAR imagery has been downloaded in this package.
2. `HANDOFFS/DEPENDENCIES.md` — inputs requested from teammates, and outputs owed to each.
3. `T02_Real_Scene_Discovery/selected-scenes.json` — chosen NASA CMR granules and IDs.
4. `T03_Scientific_Validation/validation-report.json` — catalog metadata validation only.
5. `T04_AOI_Metadata/metadata/metadata.json` — AOIs, dates and source metadata.
6. `T05_Real_Data_Access/README.md` — how to attempt real NASA Harmony download on macOS.

## Directory structure
- `T01_Data_Sources/` — source documentation.
- `T02_Real_Scene_Discovery/` — original working CMR discovery script and exact raw NASA results from the user's Mac (`raw_catalog/`), selected granules, candidate-scene report.
- `T03_Scientific_Validation/` — gatekeeper and initial report; awaits raster-level QA.
- `T04_AOI_Metadata/` — geographic bounds and metadata / M2-M5 handoff.
- `T05_Real_Data_Access/` — latest downloader and verifier, no real TIFFs currently present.
- `HANDOFFS/` — dependency list + handoff contract.
- `ARCHIVE_Previous_Packages/` — historical scripts/packages. **Do not use these for current execution**.

## One command to run latest T05 on Mac
After unzipping the main ZIP and opening a Terminal in this folder:

```bash
bash RUN_T05_ON_MAC.command
```

This calls the final T05 version from its own folder; it may need NASA Earthdata Login **locally**. No user account password or token should be shared with teammates or ChatGPT.

To check the local code before NASA downloads:

```bash
bash CHECK_LOCAL_MODULES.command
```

## Important scientific honesty
- CMR metadata contains 77 GCOV catalog hits and 65 GOFF hits from the user's observed run; it does **not** establish pixel validity or prove floods/glacier motion.
- T02 shortlisted GCOV before 2026-09-20 and 2026-10-02, plus GOFF around the same dates; use those only as candidates until data opened and QC passes.
- T05 is focused on GCOV. GOFF geospatial displacement quality is not yet tested or downloaded.
- All `.tif` scientific files are **missing** in this handoff. Do not substitute synthetic images as a NASA result.
- The ZIP preserves code versions; earlier outputs such as `t05-status.txt` are local pre-download status snapshots, not user-Mac execution proof.
