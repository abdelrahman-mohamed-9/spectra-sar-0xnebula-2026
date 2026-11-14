# SPECTRA-SAR | 0xNEBULA

NASA Space Apps Cairo 2026 — **Dancing with the SARs**.

**Research prototype:** compare SAR acquisitions, display candidate changes, rank inspection patches, and export evidence. This is *not* a confirmed flood/damage detection or emergency alert service.

## Instant judge demo

Open [judge-demo/index.html](judge-demo/index.html) (works offline). A public GitHub Pages mirror is in `/docs` after you enable Pages in Settings.

## Integrated backend

Using Python 3.12, from the repository root:

```bash
bash START.command serve --port 8770
```

Open `http://127.0.0.1:8770`, paste the locally printed operator token, select NISAR dataset, and run. Keep your token private. Use `bash START.command demo` to run the HTTP/worker evidence smoke test.

## Evidence and data

- NASA NISAR GCOV cropped Alaska pair, 17 & 29 October 2026 (mixed processing versions; no independent scientific validation). See `data/nisar/manifest.json`.
- Ritu Yadav, Modified Sen1Floods11 Dataset for Change Detection, DOI https://doi.org/10.5281/zenodo.7946594, CC BY 4.0. The Spanish hold-out demo is **Sentinel-1**, not NISAR.
- Spain model retrospective precision increases while recall falls. Unverified population/damage is **Unavailable**, not assumed to be zero.

## Documentation

- [Engineering details](README-ENGINEERING.md)
- [NASA and third-party credits](docs/SOURCES.md)
- [Full project description PDF](submission/SPECTRA-SAR-Project-Description-COMPLETE-FINAL.pdf)
- [Project description](submission/PROJECT-DESCRIPTION.md)
- [Short demo script](submission/DEMO-30-SECONDS.md)
- [Local judging checklist](submission/CAIRO-CHECKLIST.md)

**AI assistance:** ChatGPT (OpenAI) assisted with code refinement, debugging, tests and document preparation; the team must review and disclose any further AI tools used. No blanket software license has been chosen. Third-party data licenses apply independently.
