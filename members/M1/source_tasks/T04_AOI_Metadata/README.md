# SPECTRA-SAR — M1 T04 AOI & Metadata Preparation

## Delivered NOW

- `aoi/flood-aoi.geojson`: preliminary Mendenhall Valley search rectangle from T02.
- `aoi/glacier-aoi.geojson`: preliminary Mendenhall Glacier search rectangle from T02.
- `metadata/metadata.json`: NASA granules / CMR identifiers, URLs, acquisition dates, and scientific status flags.
- `metadata/handoff-m2-m5.json`: stable shared manifest for other members, with null local file paths until real SAR data exists.
- `scripts/validate_aoi.py`: zero-dependency validation of GeoJSON structure, coordinate order and manifest.
- `docs/Harmony-download-guide.md`: steps to get small *real* GCOV and GOFF rasters, avoiding huge full HDF5 downloads.

## Run on macOS

```bash
cd ~/Downloads/spectra-m1-t04
python3 scripts/validate_aoi.py
```

No dependencies. The checker does not download SAR data and **does not** claim to have proven a flood or glacier motion.

## Scope/ownership

M1 T04 metadata & provisional spatial windows COMPLETE after integrity checks. **M1 T03 remains PENDING actual raster checks**. T05 requires successfully downloading and opening an actual raster. This follows the 18-hour plan: tasks that can proceed independently should not wait on NASA sign-in/downloads.
