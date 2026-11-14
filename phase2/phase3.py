"""Phase 3 quality-aware screening, exposure and reproducible evidence."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import shapes
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely import transform
from shapely.geometry import shape
from shapely.ops import unary_union

from .impact import features, geometry_in, population_screen
from .integrity import inventory, safe
from .run_m2 import NODATA, write_json, write_raster


def quality_confidence(labels, stability, quality):
    valid = labels != 255
    interior = ndimage.binary_erosion(valid, structure=np.ones((3, 3)), border_value=0)
    residual = quality.get("holdout_p90_residual_after_px")
    geometric = 0.5 if residual is None else float(np.clip(1 - residual / 2, 0, 1))
    identifiers = quality.get("processing_identifiers", {})
    identifiers = [identifiers.get(side) for side in ("before", "after")]
    processing = 1.0 if all(identifiers) and identifiers[0] == identifiers[1] else 0.7
    confidence = np.where(valid, np.clip(stability, 0, 1) * geometric * processing, np.nan)
    retained = np.zeros(labels.shape, dtype="uint8")
    for direction in (1, 2):
        groups, _ = ndimage.label((labels == direction) & interior & (stability >= 0.99))
        sizes = np.bincount(groups.ravel())
        retained[(groups != 0) & (sizes[groups] >= 9)] = direction
    retained[~valid] = 255
    return retained, confidence, {"geometric_factor": geometric, "processing_factor": processing,
        "meaning": "threshold stability × geometric factor × processing compatibility; heuristic, not probability",
        "geometric_rule": "0.5 if unknown; otherwise clip(1 - holdout_p90_px / 2, 0, 1)",
        "processing_rule": "1 for matching known identifiers, otherwise 0.7",
        "screen_rule": "stable at all thresholds, one-pixel validity erosion, at least 9 four-connected same-sign pixels"}


def risk_score(confidence, people, buildings, roads, complete):
    if not complete or people is None:
        return None
    exposure = (min(people / 100, 1) + min(buildings / 10, 1) + min(roads / 1000, 1)) / 3
    return round(100 * confidence * exposure, 2)


def assess(root, quality, candidate_mode):
    output = root / "Phase3"
    output.mkdir()
    sources = root / "sources/geography"
    meta = json.loads((sources / "geography-source.json").read_text())
    mask = "adaptive_change_mask" if candidate_mode == "conservative" else "review_change_mask"
    stability = "confidence_stability" if candidate_mode == "conservative" else "review_stability"
    with rasterio.open(root / f"M2/{mask}.tif") as src, rasterio.open(root / f"M2/{stability}.tif") as conf:
        labels = src.read(1)
        retained, confidence, policy = quality_confidence(labels, conf.read(1, masked=True).filled(np.nan), quality)
        grid = {key: getattr(src, key) for key in ("width", "height", "crs", "transform")}
        original_crs = src.crs
        bounds = rasterio.warp.transform_bounds(src.crs, "EPSG:4326", *src.bounds)
    write_raster(output / "quality-confidence.tif", confidence, grid, nodata=NODATA, quantity="heuristic confidence, not probability")
    write_raster(output / "screened-change.tif", retained, grid, nodata=255, quantity="Phase 3 stable interior candidates")
    lon, lat = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    equal_crs = f"+proj=laea +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
    from_wgs = Transformer.from_crs("EPSG:4326", equal_crs, always_xy=True)
    from_grid = Transformer.from_crs(original_crs, equal_crs, always_xy=True)
    asset_layers = {"buildings": [], "roads": []}
    for kind, names in {"buildings": ["buildings.geojson"], "roads": ["roads-2.geojson", "roads-6.geojson", "roads-8.geojson"]}.items():
        permitted = {"Polygon", "MultiPolygon"} if kind == "buildings" else {"LineString", "MultiLineString"}
        for name in names:
            for feature in features(sources / name):
                asset_layers[kind].append(geometry_in(feature["geometry"], from_wgs, permitted))
        asset_layers[kind] = list({geometry.wkb: geometry for geometry in asset_layers[kind]}.values())
    raster_meta = meta.get("population_raster")
    complete = bool(raster_meta) and all(meta.get(kind, {}).get("coverage_verified") is True for kind in asset_layers)
    zones = []
    for direction in (1, 2):
        groups, _ = ndimage.label(retained == direction)
        for number, region in enumerate(ndimage.find_objects(groups), 1):
            if region is None:
                continue
            selected = groups[region] == number
            window = rasterio.windows.Window(region[1].start, region[0].start, selected.shape[1], selected.shape[0])
            local_transform = rasterio.windows.transform(window, grid["transform"])
            geometry = unary_union([shape(geom) for geom, _ in shapes(selected.astype("uint8"), mask=selected, transform=local_transform)])
            equal = transform(geometry, from_grid.transform, interleaved=False)
            buildings = sum(equal.intersection(asset).area > 0 for asset in asset_layers["buildings"])
            roads = unary_union([equal.intersection(asset) for asset in asset_layers["roads"]]).length
            population = population_screen(safe(sources, raster_meta["file"]), equal, equal_crs) if raster_meta else {"estimated_residents": None, "status": "NO_SPATIAL_COUNT_RASTER"}
            score = float(np.mean(confidence[region][selected]))
            risk = risk_score(score, population["estimated_residents"], buildings, roads, complete)
            zones.append({"type": "Feature", "geometry": transform_geom(original_crs, "EPSG:4326", geometry.__geo_interface__), "properties": {
                "id": f"zone-{direction}-{number}", "direction": "decrease" if direction == 1 else "increase",
                "pixels": int(selected.sum()), "area_m2": equal.area, "confidence": score,
                "confidence_kind": "uncalibrated_quality_index", "population": population,
                "mapped_buildings": buildings if meta.get("buildings", {}).get("status") != "NOT_PROVIDED" else None,
                "mapped_roads_m": roads if meta.get("roads", {}).get("status") != "NOT_PROVIDED" else None,
                "risk_score": risk, "risk_level": "unavailable" if risk is None else "high" if risk >= 60 else "medium" if risk >= 30 else "low",
                "evidence": [f"M2/{mask}.tif", f"M2/{stability}.tif", "M1/quality-report.json", "sources/geography/geography-source.json"],
                "scientific_approval": False}})
    result = {"schema_version": "3.0", "status": "EXPLORATORY", "candidate_mode": candidate_mode,
        "population_source": raster_meta,
        "bounds_wgs84": list(bounds), "zones": len(zones), "retained_pixels": int(np.isin(retained, [1, 2]).sum()),
        "input_candidate_pixels": int(np.isin(labels, [1, 2]).sum()), "confidence_policy": policy,
        "risk_policy": {"formula": "100 × confidence × mean(min(people/100,1), min(buildings/10,1), min(road_metres/1000,1))",
            "purpose": "Configurable-policy prototype for review prioritization, not calibrated hazard or expected loss",
            "thresholds": {"medium": 30, "high": 60}, "requires": "population coverage and explicit coverage_verified=true for roads and buildings"},
        "data_gaps": (["spatial_population_counts"] if not raster_meta else []) + [kind + "_verified_coverage" for kind in asset_layers if meta.get(kind, {}).get("coverage_verified") is not True],
        "limitations": ["No independent accuracy or calibrated confidence for the bundled pair", "Filtering may remove real small or boundary changes", "SAR changes alone do not identify floods or glacier displacement", "Risk is unavailable when required exposure coverage is missing"],
        "scientific_approval": False}
    if raster_meta and any(zone["properties"]["population"]["estimated_residents"] is None for zone in zones):
        result["data_gaps"].append("population_spatial_coverage")
    write_json(output / "analysis.json", result)
    write_json(output / "risk-zones.geojson", {"type": "FeatureCollection", "features": zones})
    return result


def evidence(root, files, stages):
    records = []
    previous = "0" * 64
    for name, stage in stages.items():
        record = {"stage": name, "occurred_at": datetime.now(UTC).isoformat(), "previous_sha256": previous,
            "inputs": {key: files[key] for key in stage["inputs"]},
            "outputs": {key: files[key] for key in stage["outputs"]}}
        previous = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        records.append({**record, "sha256": previous})
    code_root = Path(__file__).parent
    document = {"records": records, "head_sha256": previous,
        "code": inventory(code_root, [path.name for path in code_root.glob("*.py")]),
        "interpretation": "Local hash chain; not a digital signature or independent provider authentication"}
    write_json(root / "Phase3/processing-log.json", document)
    return document
