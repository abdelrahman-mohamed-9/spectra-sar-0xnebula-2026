# SPECTRA-SAR — M1 T02 Catalog Search

This package includes an actual NASA CMR search tool, a status report and JSON response templates, **not** invented satellite data. No NASA data has been downloaded.

## One-command search on Mac, Windows or Linux (Python 3.9+)

```bash
python3 discover_scenes.py --output .
```

On Windows, use `py -3 discover_scenes.py --output .`. No pip packages required; public CMR metadata search does not require NASA Earthdata Login (downloads may require login).

Then inspect `scene-pair.json` -> `candidate_pairs`, `goff-scenes.json` -> `candidate_granules`, and `discovery-report.md` -> query status. **Do not interpret status `CATALOG_ACCESS_BLOCKED_IN_THIS_RUNTIME` as zero results.**

## Tested locally

```bash
python3 -m unittest -v test_discovery.py
```

4 local logic tests pass. Tests use only fabricated catalog *metadata* to test the selection code; **not fabricated scientific observations**.

## Scientific caveats

The search bboxes cover Mendenhall Valley and Glacier approximately and need further AOI validation. Candidate selection checks matching orbit direction, frame, acquisition mode, polarization code and maturity where these are parseable from GCOV filenames; it is **not** equivalent to having downloaded/inspected scene data. GOFF offset quality and actual reference/secondary dates require inspecting the product itself. NISAR sensor gap 2026-07-27 to 2026-08-10 means no observations in that window. Avoid claiming flood inundation if scene time missed the high-water interval.

## Project location

Place folder at `engines/sar/t02-discovery/` or copy outputs to `data/case-study/` after confirmation. Do not commit auth credentials, large `.h5` files, or downloaded data without checking repo policy.
