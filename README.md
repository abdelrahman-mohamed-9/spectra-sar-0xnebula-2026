# SPECTRA-SAR | 0xNEBULA

**NASA Space Apps Cairo 2026 — Dancing with the SARs**

> **From satellite signals to defensible decisions.**

SPECTRA-SAR is an exploratory SAR research platform that brings together satellite change analysis, georeferenced candidate-region review, algorithm comparison, and traceable evidence. It helps analysts investigate *where radar backscatter changed*, *why a candidate was highlighted*, and *which evidence supports the result*.

**The goal is not just to compare two images. It is to make candidate changes explainable, reviewable, and reproducible.**

## Explore SPECTRA

- **Live interactive judge demo:** https://abdelrahman-mohamed-9.github.io/spectra-sar-0xnebula-2026/
- **Source code:** https://github.com/abdelrahman-mohamed-9/spectra-sar-0xnebula-2026
- **Project overview:** [submission/PROJECT-DESCRIPTION.md](submission/PROJECT-DESCRIPTION.md)
- **Project description PDF:** [submission/SPECTRA-SAR-Project-Description-COMPLETE-FINAL.pdf](submission/SPECTRA-SAR-Project-Description-COMPLETE-FINAL.pdf) (**replace with the updated AI/SI-confirmed edition before final Cairo submission**)
- **AI/SI disclosure:** [docs/AI-SI-DISCLOSURE.md](docs/AI-SI-DISCLOSURE.md)
- **NASA and external data sources:** [docs/SOURCES.md](docs/SOURCES.md)
- **Submission links and remaining steps:** [submission/PUBLIC-LINKS.md](submission/PUBLIC-LINKS.md)

The publicly hosted judge demo is a **static, interactive demonstration**. It is not a public deployment of the authenticated backend or worker.

## What the current prototype does

1. Uses documented, real satellite observations and preserves source/provenance metadata.
2. Examines candidate radar changes with geospatial processing and baseline / experimental methods.
3. Supports interactive before/after review and a candidate-region inspection queue.
4. Compares detection methods while reporting precision–recall trade-offs.
5. Exports geographic evidence and integrity references for further inspection.

The **NISAR Alaska** pair and **Sentinel-1 Spain** benchmark are separate examples and must not be merged into one event. The Alaska NISAR pair uses different product processing versions. A SHA-256 match verifies local file integrity, not satellite-source certification or scientific correctness. Reported change regions are *not* confirmed disasters, damaged buildings, or affected populations; Spain population exposure is **Unavailable** without verified, spatially aligned coverage.

## Run locally (Python 3.12 recommended)

From the repository root:

```bash
bash START.command serve --port 8770
```

Open `http://127.0.0.1:8770` and enter the locally generated operator token **privately**. Do not publish that token.

To view the static judge demo offline, open [judge-demo/index.html](judge-demo/index.html), or use the live GitHub Pages link above.

## AI/SI disclosure

**Confirmed tools:** **OpenAI ChatGPT** (code drafting/refinement, debugging, testing and technical writing), **Gamma AI** (seven-slide presentation composition and visualization), and **Manus AI** (demonstration video development / visual storytelling). Experimental machine learning also uses **scikit-learn**; these outputs are not independently validated disaster predictions. See [the detailed disclosure](docs/AI-SI-DISCLOSURE.md) for responsible-use and labeling notes.

## Scientific sources and attribution

- NASA–ISRO **NISAR L2 GCOV** Alaska cropped products; see [data/nisar/manifest.json](data/nisar/manifest.json) and [source references](docs/SOURCES.md).
- **Modified Sen1Floods11 / Sentinel-1** retrospective benchmark, Ritu Yadav, [Zenodo DOI 10.5281/zenodo.7946594](https://doi.org/10.5281/zenodo.7946594).
- Additional geospatial sources and open-source dependencies credited in [docs/SOURCES.md](docs/SOURCES.md).

This is an **exploratory research prototype**, not an operational emergency alert system. No blanket license has yet been chosen for the original repository code; third-party licenses continue to apply independently.
