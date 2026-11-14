# NASA Space Apps — SPECTRA-SAR project-page copy

**Team:** 0xNEBULA  
**Challenge:** Dancing with the SARs  
**Project name:** SPECTRA-SAR  
**Tagline:** From Satellite Signals to Defensible Decisions.

## Short summary (for the project overview)

SPECTRA-SAR transforms real satellite radar observations into an evidence-led change review workflow. It compares acquisitions, highlights candidate surface changes, organizes georeferenced patches for inspection, compares detection methods, and exports traceable evidence. Built with NASA NISAR imagery and a separate Sentinel-1 research benchmark, the prototype emphasizes model uncertainty, human oversight and scientific reproducibility—not unverified disaster claims.

## Full description

Radar satellites reveal changes that might be invisible to optical sensors under clouds or darkness. Yet a before-and-after image cannot explain whether an apparent change is meaningful, which area warrants inspection, or whether the evidence is reproducible.

**SPECTRA-SAR** is an exploratory Earth-observation intelligence platform designed around the full investigation journey: **Observe → Validate → Detect → Prioritize → Prove**.

The platform supports real satellite input provenance, geospatial raster analysis, baseline and experimental change-detection methods, a candidate-region review queue, performance comparisons that expose missed detections, and exportable supporting evidence. The interactive judge demo lets reviewers inspect the observation and selected patches; the authenticated API/worker is available in a documented local execution workflow.

The current system demonstrates NASA–ISRO **NISAR L2 GCOV** cropped observations for an Alaska study area (17 and 29 October 2026, with mixed processing versions), alongside a *separate* real **Sentinel-1 Spain** benchmark sourced from the Modified Sen1Floods11 dataset. Source identifiers, checksums, methodology and limitations are documented in the repository.

**Scientific limitation:** detected backscatter changes are exploratory candidate signals, not validated flood damage, displaced populations, glacier motion, or operational hazard forecasts. The Spain benchmark highlights real precision–recall trade-offs. Where reliable population coverage is missing, population exposure is reported as **Unavailable**.

SPECTRA's distinctive contribution is an evidence-centric process for human review, rather than another uncontextualized difference map. Future research may extend the platform to validated multi-satellite fusion, deformation products, evidence-grounded analytical assistants and more robust population/infrastructure exposure analysis. These are **proposed directions, not implemented features**.

## NASA data / resource used

- NASA–ISRO **NISAR Level 2 GCOV**; two cropped Alaska observations, 17 and 29 October 2026. Scene/granule IDs and checksums: [project manifest](../data/nisar/manifest.json).
- NISAR product information: https://nisar-docs.asf.alaska.edu/gcov/
- ASF data discovery/access documentation: https://nisar-docs.asf.alaska.edu/earthaccess/

These products were used for an exploratory radar-change workflow. They do not imply NASA validation or endorsement.

## Other data / credits

- Modified Sen1Floods11 — Ritu Yadav, Zenodo DOI: https://doi.org/10.5281/zenodo.7946594 (Sentinel-1 retrospective benchmark).
- Additional data and source attribution: [docs/SOURCES.md](../docs/SOURCES.md).
- Python, NumPy, SciPy, Rasterio, GDAL, PyProj, Shapely, FastAPI and scikit-learn are among the software tools present in the pipeline.

## AI/SI tools used

- **OpenAI ChatGPT:** code drafting/refinement, architecture and backend integration, debugging/testing, documentation and presentation text support.
- **Gamma AI:** AI-assisted design of the seven-slide presentation, layouts and visual explanation.
- **Manus AI:** AI-assisted demonstration-video production, visual scenes and storytelling.
- **scikit-learn:** experimental spatial machine-learning analysis and evaluation. Results are exploratory and are not validated disaster predictions.

All AI-generated video and illustrations included in final deliverables should carry required visible labels; generated narration should be acknowledged in its metadata/description. Human contributors remain responsible for the accuracy of code, sources and analysis.

## Links to use in the official submission

- **Public demo:** https://abdelrahman-mohamed-9.github.io/spectra-sar-0xnebula-2026/
- **Public GitHub repository:** https://github.com/abdelrahman-mohamed-9/spectra-sar-0xnebula-2026
- **Project description PDF:** https://github.com/abdelrahman-mohamed-9/spectra-sar-0xnebula-2026/blob/main/submission/SPECTRA-SAR-Project-Description-COMPLETE-FINAL.pdf — **the revised file is not at this link until the binary PDF upload is completed**
- **Official short demonstration:** add the published 30-second video URL or seven-slide presentation URL after verifying public access.
- **NASA Project Page:** add its canonical URL once published.

## Submission reminders

This markdown file is prepared content, **not evidence that the NASA form has been submitted**. Review the final wording against what the team actually demonstrated, then submit the official project-page form and verify the confirmation/receipt.
