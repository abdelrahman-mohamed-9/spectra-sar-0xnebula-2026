# SPECTRA-SAR — User Guide

**Team:** 0xNEBULA  
**Challenge:** NASA Space Apps Cairo 2026 — Dancing with the SARs  
**Release:** Phase 3.4 research prototype

> **SPECTRA helps people inspect radar-change candidates and examine the evidence behind them. It does not certify a disaster, damaged buildings, or affected population.**

## 1. Explore the project

| Mode | What it provides | Setup |
| --- | --- | --- |
| **Live public Judge Demo** | Precomputed interactive Sentinel-1 Spain benchmark, review queue, model comparison and evidence download | A web browser and internet |
| **Offline Judge Demo** | Same static demonstration on the user's computer | Open the HTML file; no Python or account |
| **Full local workspace** | FastAPI backend, independent worker, local database and bundled NISAR analysis | Python 3.12 recommended; dependencies installed on first run |

**Public Judge Demo:** https://abdelrahman-mohamed-9.github.io/spectra-sar-0xnebula-2026/

**Source code:** https://github.com/abdelrahman-mohamed-9/spectra-sar-0xnebula-2026

The public GitHub Pages site is a **static frontend**: it does not run the Python backend, worker, or local database.

## 2. Interactive Judge Demo — five-minute walkthrough

1. Open the public demo link. You do not need an access token.
2. Start with the **Before / After** radar comparison. These are retrospective **Sentinel-1 Spain** observations, not the separate NASA NISAR Alaska pair.
3. Select **Fixed Threshold** and then **Spatial ML**. Compare candidate masks and published precision/recall metrics; a model can reduce false positives while missing more reference cases.
4. In the **Priority Review Queue**, choose a region/patch and examine its location and review details. The review order is **not** a validated emergency risk ranking.
5. Explore the **Radar Difference**, **Published Reference** and other views where available.
6. Use the export controls for **Mission Brief JSON**, **Comparison CSV**, or **Selected Region** evidence.
7. Explain the main limitation: a highlighted radar-change candidate is not automatically a confirmed flood, damaged building, or affected person.

**If exposure is Unavailable**, that means suitable verified population data is missing. It does *not* mean the population is zero.

## 3. Offline demo

Extract the project release and open the following file in a browser:

    SPECTRA-Phase3/judge-demo/index.html

This is a portable, precomputed demo. It does **not** submit a new Python processing job. Use the full local workspace to run analysis.

## 4. Full local workspace — macOS or Linux

### Prerequisites

- Python **3.12** is the tested version; 3.13/3.14 may be accepted by the launcher but were not fully tested in this release.
- Full project archive or repository extracted on the computer.
- Internet for the first dependency installation.
- An available local TCP port; 8765 is the default.

### Start the local backend

Open Terminal in the project directory. On macOS, if the released ZIP is extracted into Downloads:

    cd ~/Downloads/SPECTRA-Phase3
    bash START.command serve --port 8770

Open the following URL on the same computer:

    http://127.0.0.1:8770

### Connect with an operator token

The launcher prints a private **Access token** in its terminal output. Paste only the token into the browser's **Access token** field and press **Connect**.

On macOS, to copy the saved token again without printing it:

    tr -d '\r\n' < ~/Downloads/SPECTRA-Phase3/state/operator-token.txt | pbcopy

**Never share the token** in screenshots, GitHub, NASA submissions, or public logs.

### Run bundled NISAR exploratory analysis

1. In the connected dashboard, choose a **SOURCE PAIR**. Depending on the release, the population-aware variant may be named **nisar-oct2026-ghsl2025**.
2. Select a **CANDIDATE SCREEN** — for example **Conservative** or **Broader review**.
3. Click **Run analysis**. Keep the backend terminal open while the independent worker runs.
4. Look at **Recent analyses** and click **Refresh** until the job completes, or reports an error.
5. Inspect **Before / after**, **Conservative**, **Broader review**, **Review priority**, **Model comparison** and **Download & inspect** as available.
6. Download a report or evidence artifact and review its source information.

Switching visualization tabs **after** running does not recalculate the saved job. To change the selected analysis screen, run a new job.

To stop the backend and worker, press **Ctrl+C** in the launching Terminal window.

## 5. Test the installation

From the project root:

    bash START.command test
    bash START.command demo

The first command runs automated regression checks. The second exercises a local API/worker job, retrieves evidence files, and checks hashes. **Successful software tests are not independent scientific validation.**

## 6. Interpret the data correctly

**NISAR / Alaska:** The bundled NASA–ISRO NISAR GCOV example uses two cropped acquisitions dated **17 and 29 October 2026**. Their processing versions differ, and independent disaster labels and full comparability verification are missing. Source identities and checksums are documented in [data/nisar/manifest.json](../data/nisar/manifest.json).

**Sentinel-1 / Spain:** A distinct retrospective benchmark from the Modified Sen1Floods11 collection, credited to Ritu Yadav ([Zenodo DOI 10.5281/zenodo.7946594](https://doi.org/10.5281/zenodo.7946594)).

**SHA-256:** A matching digest verifies byte-for-byte consistency of local copies, not disaster severity, satellite authentication or scientific model accuracy.

**Population:** Exposure should be reported **Unavailable** when matching verified coverage is missing — never as an invented number.

## 7. Troubleshooting

| Symptom | Recommended response |
| --- | --- |
| **Address already in use / Errno 48** | A process already owns the port. Stop only a confirmed old SPECTRA process or choose another port such as 8770. |
| **Invalid bearer token (HTTP 401)** | Copy the token for the **currently running** local backend; reconnect after refreshing the page. |
| **Non ISO-8859-1 code point error** | Paste only the raw token, not a sentence or Unicode symbols. |
| **First launch package installation fails** | Use tested Python 3.12, check internet and installation logs. |
| **Public site shows only frontend** | Expected: GitHub Pages cannot run local Python/FastAPI workers. |
| **Population Unavailable** | A valid aligned exposure layer is absent. Do not substitute zero. |
| **Job pending or error** | Ensure the worker remains running. Inspect local state/logs/worker.log privately; redact secrets before sharing. |

## 8. Credits, privacy and further reading

- [NASA and third-party sources](SOURCES.md)
- [AI/SI disclosure (ChatGPT, Gamma AI, Manus AI)](AI-SI-DISCLOSURE.md)
- [Engineering integration and operations](INTEGRATION-AND-OPERATIONS.md)
- [Data contracts](DATA-CONTRACTS.md)
- [Official submission overview](../submission/NASA-PROJECT-PAGE-COPY.md)

Do not upload the local state directory, operator tokens, private logs, credentials, or unreviewed data. Any AI-generated media in the final submission should carry the required labels and attributions.

---

**SPECTRA-SAR:** *See the Change. Question the Signal. Trust the Evidence.*

*Exploratory research prototype. Independent scientific validation is required before operational use.*