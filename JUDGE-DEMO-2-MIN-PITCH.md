# SPECTRA · Two-minute judge demonstration (English)

**Opening (0:00–0:20).** "Satellite radar works through clouds and darkness, but an image difference is not a decision. SPECTRA turns the difference into a traceable *review queue*. This is a research prototype, not a disaster warning system."

**Before / After (0:20–0:40).** Open `judge-demo/index.html` and move the **Swipe images** slider. "Both are genuine Sentinel-1 observations from a published Spain benchmark. The product shows a shared radar grid, not an optical photograph. The Spain benchmark is separate from our real NISAR Alaska pipeline."

**Review priorities (0:40–1:05).** Click **Spatial ML**; choose the first review patch. "SPECTRA finds contiguous radar candidates and orders them by area to help a reviewer focus. The coordinates, footprint, backscatter difference, and source filenames can be inspected and exported. The ranking does not use the held-out labels."

**What-if radius (1:05–1:20).** Move **Inspection radius** from 0 to 150 m. "This changes the field-review footprint. It does not magically estimate nearby people; a georeferenced population raster and source metadata are necessary for population overlays."

**Scientific trade-off (1:20–1:45).** Switch between **Fixed threshold** and **Spatial ML**. "On this held-out Spain tile the ML screen improves precision from 60.9% to 79.2%, but recall drops from 56.7% to 26.6%. A model that raises fewer false alarms can still miss important signals. SPECTRA shows this trade-off rather than hiding it."

**Evidence and close (1:45–2:00).** Export **selected region JSON** and **comparison CSV**; open the hash manifest. "Every derived review can be traced to source rasters using SHA-256 receipts. We keep unvalidated claims unavailable. Our innovation is actionable triage with transparent uncertainty and reproducible evidence."

## Expected judge questions and grounded answers

- **Is this a flood prediction?** No. The source includes published retrospective flood/water labels; our detector output is an exploratory candidate screen, not operational forecasting or an assessment of physical damage.
- **Is the model independently validated?** Only on one held-out Spain chip from this external benchmark, with Ghana and USA as training chips. Generalization remains unproven.
- **How many people were affected?** Unknown. The supplied source ZIP lacks a verified population raster for the Spanish tile. The tool supports plugging in a documented people-per-cell raster with spatial coverage checks, but it never reports confirmed casualties or impacts.
- **Are the SHA-256 hashes NASA signatures?** No. They verify local file consistency. Provider provenance and independently signed authenticity are separate requirements.
- **Why do we need the original SPECTRA app?** The Mission Studio is a one-click offline story for judging; the original app remains the source-workflow integration of M1–M6, jobs, processing outputs and evidence.
