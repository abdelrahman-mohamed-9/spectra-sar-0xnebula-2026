# SPECTRA 3.4 — User guide

**New: instant, offline judging demo.** Open `judge-demo/index.html` or double-click `OPEN-JUDGE-DEMO.command` (macOS) / `OPEN-JUDGE-DEMO-WINDOWS.cmd` (Windows). No token, server or Python required. See `JUDGE-START-HERE.txt`. The full SPECTRA 3.3 processing workflow below is retained.


## Open the program on Windows

1. Extract the ZIP using **Extract All**. Do not run inside the ZIP viewer.
2. Open the extracted folder and double-click **START-WINDOWS.cmd**.
3. Python must already be installed. The first start installs dependencies and
   needs internet access. Wait for the workspace URL and access token.
4. Keep the terminal open. The browser opens http://127.0.0.1:8765.
5. Copy the printed access token into **Access token**, then click **Connect**.
   The token belongs to this local workspace; keep it private.
6. Select **nisar-oct2026-ghsl2025** to include the bundled population model.
   Click **Run analysis** and wait for completion.

## What you see

- **Compare acquisitions:** swipe between actual before/after SAR images.
- **Risk review map:** select a retained change region; filter by quality and
  switch between risk and confidence colors. Grey means risk is unavailable.
- **Results explained:** the area, direction of backscatter change, quality,
  available population/building/road exposure and evidence for each region.
- **Review alerts:** rule-based review requests with a persistent reviewed state.
- **Compare analyses:** compare another completed run covering the same area.
  Reprocessing the same images compares settings, not different observation dates.
- **Download report:** a standalone English HTML report containing images,
  explanations, alerts and evidence hashes. Print it to save as PDF.
- **Review glacier movement:** optional prepared displacement ZIP upload.
  Results persist with the run and can be downloaded as separate JSON.
- **Evidence & results:** source snapshots, files, processing history and hashes.

All current application text and generated HTML reports are English.
Historical documentation is retained for provenance and may describe older releases.

## Scientific status

The bundled pair is real NISAR imagery from October 17 and 29, 2026.
Its location is interior Alaska, not Mendenhall. No real glacier displacement
measurements have been supplied or validated.

The population layer is GHS-POP 2025: a modeled projection, not observed people.
Its valid cells in this crop are zero. That is not proof that no people are present.
Building/road completeness and independent reference labels remain unresolved.
Incomplete risk is **Unavailable**; confidence is an uncalibrated quality score.

Glacier input details are in **GLACIER-INPUTS.md**. Native GOFF HDF5 extraction,
stable-ground correction, full surface velocity inversion and scientific
validation are not automated in this release.

## Member deliverables

| Member | Implemented | Outstanding evidence |
|---|---|---|
| M1 | SAR filtering, common grids, alignment diagnostics, reliability report | Independent geometry checks and terrain masks |
| M2 | Change screening, stability, connected regions and quality index | Local independent labels and calibrated confidence |
| M3 | Population and mapped-asset overlap, coverage-aware experimental risk | Verified complete building/road coverage |
| M4 | Source snapshots, SHA-256 receipts, processing chain, verified downloads | Independent provider signatures are not supplied |
| M5 | Persistent jobs, APIs, ownership checks, alert reviews, glacier supplements | Operational deployment is outside this local release |
| M6 | English comparison dashboard, map, explanations, alerts and portable reports | Actual glacier displacement results require inputs |

## Verification

See **reports/phase3.3-tests.txt** and **reports/phase3.3-backend-tests.txt**.
Synthetic glacier tests establish software behavior only; they do not establish
accuracy on a real glacier. Historical baseline-failure reports are retained;
the Windows handoff and integrated contract export issues are fixed in 3.3.
