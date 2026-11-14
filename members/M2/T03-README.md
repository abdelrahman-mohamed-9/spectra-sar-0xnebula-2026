# SPECTRA-SAR M2 — T03 SAR Speckle Noise Filtering

## Status
Software implementation + automated tests. **Not validated yet on actual Sentinel-1 data.** All synthetic unit fixtures are code QA only and MUST NOT be described as real satellite before/after evidence.

## What it does
- Reads T01/T02 manifest-driven **unfiltered** Sentinel-1 **RTC gamma0 linear POWER** GeoTIFFs from M1.
- Runs T02 scientific preflight; REJECT stops, WARNING stops by default (`--allow-warning` requires explicit operator decision).
- Runs mask-aware local-statistics **Lee-family** spatial filter independently on before/after imagery; ignores invalid/layover-shadow areas.
- Uses overlap/halo around every tile for seam-free filtering of larger rasters.
- Outputs spatially registered Float32 GeoTIFFs with NoData=-9999, tags and JSON QA report.
- Filtering DOES NOT fix co-registration or identify change: T04 and T05 handle those.

## Setup / test
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

## Run with real data from M1
```bash
python filters.py /absolute/path/to/real_M1_pair --out /absolute/path/to/M2_filtered --polarization VV --window 7 --looks 4 --allow-warning
```
`--looks` is a tuning assumption, **not measured ENL**. Infer/tune it from product metadata or homogeneous areas. ASF HyP3 can deliver *already filtered* products; **M1 must use unfiltered RTC** to avoid double filtering. The default Lee-family filter is a transparent baseline; it is not the proprietary/Enhanced Lee implementation.

## Compare real before and after imagery
```bash
python compare_filter.py /absolute/path/to/real_M1_pair /absolute/path/to/M2_filtered --side before --polarization VV
```
Creates `before_VV_before_after.png`, depicting the **same real acquisition** before and after speckle filtering, and summary metrics for a chosen homogenous ROI. These are not temporal before/after acquisitions. Full-scene global metrics alone cannot establish quality; visually inspect edges, water boundaries, strong scatterers, and measure ENL on representative homogenous regions.

## M1 handoff
A T02-valid `manifest.json`, its two geocoded aligned RTC backscatter images in **linear power**, valid-data masks, optional layover-shadow masks and source acquisition metadata. M1 should specify any preexisting speckle filtering and looks/ENL information. Do not claim scientifically validated results until real dataset evaluation.

## Reference
- ASF HyP3 RTC products and product guide: https://hyp3-docs.asf.alaska.edu/products/ and https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/
- DLR SAR statistics and Equivalent Number of Looks: https://elib.dlr.de/70934/1/phdthese_DanielaEspinozal.pdf
