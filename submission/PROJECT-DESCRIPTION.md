# SPECTRA-SAR — 0xNEBULA

**Challenge:** Dancing with the SARs  
**Event:** NASA Space Apps Cairo 2026  
**Tagline:** From Satellite Signals to Defensible Decisions.

## The decision gap

Satellite radar can reveal changes in Earth's surface under cloud cover and darkness, but a before/after image alone does not tell an analyst which changes deserve inspection, how reliable a model is, or whether its output can be independently checked.

**SPECTRA-SAR turns radar-change candidates into a structured review workflow:** Observe → Validate → Detect → Prioritize → Prove.

## Working features

- Compare real before-and-after satellite radar observations.
- Inspect candidate changes and georeferenced regions through the interactive Mission Review Studio.
- Compare fixed-threshold detection with experimental spatial machine-learning approaches, showing trade-offs rather than hiding errors.
- Organize candidate regions into a review workload based on contiguous-region size, not a validated disaster-risk score.
- Export supporting coordinates, review summaries and source-integrity evidence.
- Run an authenticated local backend / API for exploratory processing.

The **live judge demo** is a static demonstration. The complete processing backend must be run locally; it is not hosted publicly.

## Sources and verified scope

- **NASA–ISRO NISAR L2 GCOV:** two documented cropped Alaska radar acquisitions, dated 17 and 29 October 2026, with their exact identifiers, raster metadata and SHA-256 checks recorded in the repository. The two products have different processing-version identifiers; scientific comparability is not independently certified.
- **Sentinel-1 Spain retrospective example:** a separate hold-out comparison from the Modified Sen1Floods11 collection, credited to Ritu Yadav (Zenodo DOI 10.5281/zenodo.7946594). The experimental model has a precision–recall trade-off; it should not be described as superior on all measures.
- **Population and infrastructure overlays:** coverage is dataset- and geography-dependent. No unverified number of affected people or damaged buildings is claimed. For the current Spain example, population exposure is **Unavailable**.

Local raster SHA-256 verification demonstrates file consistency across handoffs, **not** confirmation of disaster class, satellite-origin authenticity, or scientific model accuracy.

## What's different?

Many Earth-observation demos end with a colored difference map. SPECTRA additionally exposes an inspection queue, compares model behavior, documents provenance and uncertainty, and keeps results open to human challenge and evidence review.

## Future research (not implemented)

Multi-satellite fusion, validated deformation/offset measurements, evidence-grounded analytical assistants, richer population/infrastructure exposure models, and multi-temporal predictive monitoring are future research directions—not current capabilities.

## Tools and responsible AI/SI use

**OpenAI ChatGPT** assisted software engineering, debugging, tests and technical content; **Gamma AI** was used for the seven-slide presentation and visualization; **Manus AI** helped produce demonstration video/storytelling materials. Experimental scientific modeling uses scikit-learn. Human review, accurate attribution, and explicit labeling of AI-generated media remain required.

See [full AI/SI disclosure](../docs/AI-SI-DISCLOSURE.md) and [NASA / external credits](../docs/SOURCES.md).

## Public links

- **Source code:** https://github.com/abdelrahman-mohamed-9/spectra-sar-0xnebula-2026
- **Interactive demo:** https://abdelrahman-mohamed-9.github.io/spectra-sar-0xnebula-2026/
- **Project description PDF:** [repository PDF](SPECTRA-SAR-Project-Description-COMPLETE-FINAL.pdf) — replace with the confirmed AI/SI edition before submission.
- **Official ≤30 second demo video or ≤7 slide deck:** public submission link to be attached after publication.
- **NASA Space Apps project page:** official project page URL not yet supplied.

**For judges:** The project is a research prototype, not an operational flood/damage warning service.
