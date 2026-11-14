# Glacier movement inputs

The existing GCOV pair is already bundled. Do not download it again.
It measures radar backscatter change, not glacier velocity. The bundled AOI
is in interior Alaska and is not Mendenhall; a glacier boundary must establish
whether a glacier overlaps an analysis before calling its result glacier change.

## What to send

1. The original **NISAR GOFF .h5** product covering the intended glacier.
   One GOFF product describes offsets between two acquisitions; keep its
   reference and secondary timestamps, polarization, quality layers and metadata.
   Send the download/catalog link as well. Do not send your account password.
2. Glacier outlines as **GeoJSON**, **GeoPackage**, or a complete zipped shapefile
   (.shp, .shx, .dbf, .prj), with source and observation date.
3. If available, independent velocity measurements or a published velocity map
   covering the same glacier and dates, with uncertainty and source.
   These are required for validation, not for exploratory processing.
4. For displacement correction, stable-ground boundaries and terrain/layover/
   shadow masks are useful. Their absence remains an explicit limitation.

If choosing a different glacier, also supply a before/after SAR pair for that
glacier to create a separate dataset. Do not attach it to the existing Alaska run.

Official guide: https://nisar-docs.asf.alaska.edu/goff/
Data search: https://search.asf.alaska.edu/

## Prepared bundle supported by the app

Raw HDF5 import is not automatic in this release. A data preparer must extract
the correct GOFF layer and confirm units, sign convention, dates and geometry.
The app accepts a ZIP containing exactly these five root-level files:

- manifest.json
- along_track.tif: signed along-track displacement, meters
- slant_range.tif: signed slant-range displacement, meters
- snr.tif: dimensionless signal-to-noise ratio
- glacier_mask.tif: 1 inside independently sourced glacier outlines, 0 outside

All rasters must be single-band GeoTIFFs on exactly the same grid and CRS,
with nodata declared. The coverage must overlap the selected SAR analysis.
Maximum: one million cells per layer, 32 MB ZIP, 128 MB expanded.
Mask alignment must use nearest-neighbor resampling. Do not resample offsets
without recording the method and source grid. Do not rename pixel offsets to
meters without applying the documented product-specific conversion.

Example manifest (replace the example values with real source metadata):

```json
{
  "source_product": "Original GOFF granule identifier",
  "source_url": "https://provider.example/catalog/granule",
  "glacier_source": "Outline dataset identifier, version and date",
  "reference_time": "2026-10-17T00:00:00Z",
  "secondary_time": "2026-10-29T00:00:00Z",
  "units": "meters",
  "offset_convention": "secondary_minus_reference",
  "preparation": "Record layer paths, band, polarization and any conversion"
}
```

Open a completed analysis, then use **Review glacier movement** to upload.
The server preserves the original bundle, source hashes and result, linked to
the owning run. Reloading the run checks integrity and restores these results.
Download the separate displacement JSON for its statistics and evidence.
The backscatter HTML report does not include displacement supplements.

## What the result means

The app screens SNR >= 5 and local median residual outliers, then divides
signed displacement components by elapsed acquisition days. Thresholds are
exploratory. Spatial percentiles are not confidence intervals.
These radar-coordinate components are **not full surface speed** or east/north
velocity. Stable-ground correction, uncertainty propagation, independent
validation and full velocity inversion remain future scientific work.
No glacier observations or calibrated confidence are fabricated.
