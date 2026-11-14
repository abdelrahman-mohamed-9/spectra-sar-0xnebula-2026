# SPECTRA-SAR / 0xNEBULA — Data, Software & AI/SI Credits

**Status:** Team-review copy. Confirm all final media tools, redistributed asset permissions and submission links before public release.

## NASA data used

- **NASA–ISRO NISAR, Level 2 GCOV (HHHH):** Two actual user-supplied Alaska raster extracts dated **2026-10-17** and **2026-10-29**. Product metadata, complete acquisition IDs, input raster paths and processing versions are maintained in `data/nisar/manifest.json`. NISAR data provider: https://nisar.asf.earthdatacloud.nasa.gov/ ; product guide: https://nisar-docs.asf.alaska.edu/gcov/ . The before and after products have **different processing versions** (P05023 provisional and P05036): this is exploratory screening, not a scientifically validated event comparison. Source identifiers/hashes retained locally are not provider cryptographic signatures.

## External datasets and geographical references

| Resource / owner | Role and attribution |
|---|---|
| **Modified Sen1Floods11 Dataset for Change Detection** — Ritu Yadav, Zenodo record 7946594 | Separate before/after **Sentinel-1** chips and held-out evaluation labels from Ghana, USA and Spain. DOI: https://doi.org/10.5281/zenodo.7946594 . Project source receipt records **CC BY 4.0**; confirm current reuse terms and retain credit when redistributing. |
| **GHS-POP R2023A** — European Commission Joint Research Centre | Modeled residential-population projection for 2025, 100 m grid, used as a contextual input in Alaska. Citation: Schiavina, Freire, Carioli & MacManus (2023), DOI https://doi.org/10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE ; https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php . **CC BY 4.0.** A sampled population sum of zero is not a confirmed absence of people. |
| **TIGERweb** — U.S. Census Bureau | Census 2020 population blocks and transportation layers queried in Alaska. Full parameters/endpoints: `data/geography/geography-source.json` . https://tigerweb.geo.census.gov/ |
| **USA Structures** — FEMA / ORNL, served via Esri | Building-footprint spatial context queried for Alaska. Endpoint and query scope: `data/geography/geography-source.json` . https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/USA_Structures_View/FeatureServer/0 |

## Scientific software and development tools

- **Python**, **NumPy**, **SciPy**, **rasterio/GDAL**, **pyproj**, **Shapely**, **scikit-image**, **scikit-learn**: numerical, geospatial and candidate change / evaluation operations.
- **FastAPI**, **Uvicorn**, **Pydantic**, **SQLAlchemy**, **SQLite**: local API, validation, processing tasks and persistence.
- **HTML/CSS/JavaScript**, **Pillow**: review interface and image presentation.
- **pytest** and associated Python testing packages: automated regression and HTTP checks.
- Refer to `requirements.txt`, `requirements-phase3.txt` and `backend/pyproject.toml` for exact dependencies; each dependency remains subject to its own license. Public availability is not a blanket license for third-party datasets or code.

## AI/SI use (confirmed from project collaboration)

**OpenAI ChatGPT** provided assistance with source code authoring/revision, Python and API troubleshooting, tests, integration workflows, documentation, and editorial drafting of the project description. Team members must validate functionality, scientific interpretation and compliance before submission.

**Other AI/SI tools: not yet verified.** If the final submission uses Manus, Gemini, Claude, text-to-speech, image or video generation, or additional assistants, add exact tool names, tasks and affected files before submitting. Do not list a tool as used only because a prompt was prepared for it.

### AI-generated artifact labeling rules — Cairo 2026 guidance

- Generated **images/video**: visible watermark identifying AI/SI generation on generated parts.
- Generated **audio**: note AI/SI generation in description and metadata.
- Generated **code/data**: acknowledge AI assistance in artifact descriptions and associated metadata.
- AI-generated media must **not use or modify NASA branding or insignia**.
- Confirm the challenge-solving idea was conceived by the team, as required by the 2026 guidance, and review all factual claims.

## Scientific limits

Radar change pixels are *candidates for further investigation*, not confirmed flooding, infrastructure damage, victims or glacier displacement. The NISAR Alaska example is separate from the Sentinel-1 Spain benchmark; their labels, sensors, processing settings, and measured performance cannot be conflated. Population estimates require source-appropriate spatial overlap and uncertainty analysis.

---
*Please cross-check any final media assets and licenses before publishing this statement on the project page and GitHub.*
