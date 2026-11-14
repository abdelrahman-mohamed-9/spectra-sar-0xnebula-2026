"""M3 screening against named geographic sources with explicit coverage limits."""

import json

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import shapes
from rasterio.warp import transform_bounds, transform_geom
from rasterio.windows import Window, from_bounds
from shapely import transform
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import unary_union

from .run_m2 import write_json


def features(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    if (
        document.get("type") != "FeatureCollection"
        or not isinstance(document.get("features"), list)
        or document.get("exceededTransferLimit")
        or document.get("error")
    ):
        raise ValueError("Incomplete or invalid geographic source")
    return document["features"]


def feature_collection(items):
    return {"type": "FeatureCollection", "features": items}


def geometry_in(geometry, transformer, permitted):
    g = shape(geometry)
    if g.is_empty or not g.is_valid or g.geom_type not in permitted:
        raise ValueError(f"Invalid input geometry: {g.geom_type}")
    return transform(g, transformer.transform, interleaved=False)


def population_screen(path, footprint, equal_crs="EPSG:3338"):
    """Area-weighted modelled residents for a complete count-per-cell raster."""
    if footprint.is_empty:
        return {"status": "NO_CANDIDATES", "estimated_residents": 0.0, "coverage_fraction": 1.0}
    with rasterio.open(path) as ds:
        if (
            ds.count != 1
            or ds.crs is None
            or ds.transform.b
            or ds.transform.d
            or ds.transform.a <= 0
            or ds.transform.e >= 0
        ):
            raise ValueError("Population source must have one band on a north-up grid")
        src_bounds = transform_bounds(equal_crs, ds.crs, *footprint.bounds, densify_pts=41)
        requested = from_bounds(*src_bounds, transform=ds.transform)
        c0 = max(0, int(np.floor(requested.col_off)))
        r0 = max(0, int(np.floor(requested.row_off)))
        c1 = min(ds.width, int(np.ceil(requested.col_off + requested.width)))
        r1 = min(ds.height, int(np.ceil(requested.row_off + requested.height)))
        if c1 <= c0 or r1 <= r0:
            return {
                "status": "NO_SPATIAL_COVERAGE",
                "estimated_residents": None,
                "coverage_fraction": 0.0,
            }
        if (c1 - c0) * (r1 - r0) > 250_000:
            raise ValueError("Crop population inputs to the AOI before analysis")
        values = ds.read(1, window=Window(c0, r0, c1 - c0, r1 - r0), masked=True)
        transform_cell = Transformer.from_crs(ds.crs, equal_crs, always_xy=True)
        observed = 0.0
        estimated = 0.0
        for row, col in np.argwhere(~np.ma.getmaskarray(values) & np.isfinite(values.data)):
            value = float(values[row, col])
            if value < 0:
                raise ValueError("Population counts must be nonnegative")
            r, c = int(row) + r0, int(col) + c0
            polygon = Polygon(
                [
                    ds.transform * pixel
                    for pixel in (
                        (c, r),
                        (c + 1, r),
                        (c + 1, r + 1),
                        (c, r + 1),
                    )
                ]
            )
            cell = transform(polygon, transform_cell.transform, interleaved=False)
            if not cell.is_valid or cell.area <= 0:
                raise ValueError("Invalid population cell footprint")
            area = footprint.intersection(cell).area
            observed += area
            estimated += value * area / cell.area
    fraction = min(1.0, observed / footprint.area)
    if fraction < 0.999:
        return {
            "status": "INCOMPLETE_SPATIAL_COVERAGE",
            "estimated_residents": None,
            "coverage_fraction": fraction,
        }
    return {
        "status": "AREA_WEIGHTED_MODEL_ESTIMATE",
        "estimated_residents": estimated,
        "coverage_fraction": fraction,
    }


def assess(m2, sources, output, candidate_mode="conservative"):
    """Compute mapped intersections and coarse census context, with review priorities."""
    if candidate_mode not in {"conservative", "review"}:
        raise ValueError("Unknown candidate mode")
    mask_name = "adaptive_change_mask.tif" if candidate_mode == "conservative" else "review_change_mask.tif"
    stability_name = "confidence_stability.tif" if candidate_mode == "conservative" else "review_stability.tif"
    output.mkdir()
    with (
        rasterio.open(m2 / mask_name) as labels,
        rasterio.open(m2 / stability_name) as stability,
    ):
        if (labels.crs, labels.transform, labels.shape) != (
            stability.crs,
            stability.transform,
            stability.shape,
        ):
            raise ValueError("M3 mask and stability grids do not match")
        data = labels.read(1)
        valid = data != 255
        candidate = np.isin(data, [1, 2])
        conf = stability.read(1, masked=True)
        if np.any(candidate & np.ma.getmaskarray(conf)):
            raise ValueError("Candidates are missing stability values")
        bounds = rasterio.warp.transform_bounds(labels.crs, "EPSG:4326", *labels.bounds)
        lon, lat = (bounds[0]+bounds[2])/2, (bounds[1]+bounds[3])/2
        equal_crs = "EPSG:3338" if -180 <= lon <= -130 and 50 <= lat <= 75 else f"+proj=laea +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs"
        equal = Transformer.from_crs(labels.crs, equal_crs, always_xy=True)

        def to_equal(geometry):
            return transform(geometry, equal.transform, interleaved=False)

        from_wgs = Transformer.from_crs("EPSG:4326", equal_crs, always_xy=True)
        to_wgs = Transformer.from_crs(equal_crs, "EPSG:4326", always_xy=True)
        risk = np.full(labels.shape, 255, dtype="uint8")
        risk[valid] = 0
        risk[candidate & (conf.filled(0) < 0.99)] = 1
        risk[candidate & (conf.filled(0) >= 0.99)] = 2

        def region(mask):
            return unary_union(
                [
                    to_equal(shape(g))
                    for g, _ in shapes(
                        mask.astype("uint8"),
                        mask=mask,
                        transform=labels.transform,
                        connectivity=4,
                    )
                ]
            )

        footprint = region(candidate)
        coverage = region(valid)
        grid_outline = Polygon(
            [
                labels.transform * pt
                for pt in (
                    (0, 0),
                    (labels.width, 0),
                    (labels.width, labels.height),
                    (0, labels.height),
                )
            ]
        )
        if not coverage.is_valid or not footprint.is_valid:
            raise ValueError("Candidate or coverage geometry invalid")
        bounds = rasterio.warp.transform_bounds(labels.crs, "EPSG:4326", *labels.bounds)
        profile = labels.profile.copy()
        with rasterio.open(output / "review-priority.tif", "w", **profile) as dst:
            dst.write(risk, 1)
            dst.update_tags(
                classes="0:no_candidate;1:threshold_sensitive;2:threshold_stable;255:nodata",
                scientific_approval="false",
                interpretation="review_priority_not_hazard_risk",
            )
        zones = []
        for geom, code in shapes(risk, mask=candidate, transform=labels.transform, connectivity=4):
            zones.append(
                {
                    "type": "Feature",
                    "geometry": transform_geom(labels.crs, "EPSG:4326", geom),
                    "properties": {"priority": int(code), "scientific_approval": False},
                }
            )

    paths = {
        "population": ["population.geojson"],
        "roads": ["roads-2.geojson", "roads-6.geojson", "roads-8.geojson"],
        "buildings": ["buildings.geojson"],
    }
    source_meta = json.loads((sources / "geography-source.json").read_text())
    west, south, east, north = source_meta["query_bbox_wgs84"]
    if not (west <= bounds[0] and south <= bounds[1] and east >= bounds[2] and north >= bounds[3]):
        raise ValueError("Geographic source query did not cover the SAR grid")
    population = {
        "status": "NO_SPATIAL_COUNT_RASTER",
        "estimated_residents": None,
        "coverage_fraction": None,
    }
    raster_meta = source_meta.get("population_raster")
    if raster_meta:
        from .integrity import safe

        if raster_meta.get("units") != "people_per_cell" or not raster_meta.get("source"):
            raise ValueError("Population raster requires provenance and people_per_cell units")
        population = population_screen(safe(sources, raster_meta["file"]), footprint, equal_crs)
    output_features, context, clipped_roads = [], [], []
    population_coverage = []
    building_ids = set()
    mapped_counts = {}
    for kind, names in paths.items():
        mapped_counts[kind] = 0
        for name in names:
            for feature in features(sources / name):
                allowed = (
                    {"LineString", "MultiLineString"}
                    if kind == "roads"
                    else {"Polygon", "MultiPolygon"}
                )
                g = geometry_in(feature["geometry"], from_wgs, allowed)
                if not g.intersects(coverage):
                    continue
                mapped_counts[kind] += 1
                props = feature.get("properties") or {}
                intersection = g.intersection(footprint)
                if kind == "population":
                    population_coverage.append(g.intersection(coverage))
                    people = props["POP100"]
                    land_area = props["AREALAND"]
                    if type(people) is not int or people < 0 or land_area < 0:
                        raise ValueError("Invalid census population or land area")
                    context.append(
                        {
                            "block": props["GEOID"],
                            "census_2020_population": people,
                            "block_land_km2": land_area / 1e6,
                            "block_density_people_per_land_km2": people * 1e6 / land_area
                            if land_area
                            else None,
                            "candidate_overlap_m2": intersection.area,
                            "candidate_fraction_of_block_geometry": intersection.area / g.area,
                        }
                    )
                elif kind == "buildings" and intersection.area > 0:
                    building_ids.add(str(props.get("OBJECTID", feature.get("id"))))
                elif kind == "roads" and intersection.length > 0:
                    clipped_roads.append(intersection)
                else:
                    continue
                if not intersection.is_empty:
                    output_features.append(
                        {
                            "type": "Feature",
                            "geometry": mapping(
                                transform(intersection, to_wgs.transform, interleaved=False)
                            ),
                            "properties": {
                                "layer": kind,
                                "interpretation": "spatial_overlap_only",
                            },
                        }
                    )
    census_coverage = unary_union(population_coverage).area / coverage.area if coverage.area else 0
    report = {
        "status": "EXPLORATORY_EXPOSURE_SCREEN",
        "scientific_approval": False,
        "impact_confirmed": False,
        "candidate_mode": candidate_mode,
        "area_crs": equal_crs,
        "candidate_area_m2": footprint.area,
        "candidate_area_m2_alaska_albers": footprint.area if equal_crs == "EPSG:3338" else None,
        "candidate_area_fraction_of_valid_grid": footprint.area / coverage.area,
        "valid_coverage_m2": coverage.area,
        "full_grid_area_m2": to_equal(grid_outline).area,
        "mapped_assets_in_valid_grid": mapped_counts,
        "mapped_road_overlap_m": unary_union(clipped_roads).length,
        "mapped_buildings_intersecting": len(building_ids),
        "census_coverage_fraction": min(1.0, census_coverage),
        "census_block_context": context,
        "estimated_residents_exposed": population["estimated_residents"],
        "population_raster_screen": population,
        "priority_pixel_counts": {
            "threshold_sensitive": int((risk == 1).sum()),
            "threshold_stable": int((risk == 2).sum()),
        },
        "source_metadata": source_meta,
        "recommendations": [
            "Review threshold-stable candidates first against independent imagery and local reports.",
            "Use a matched high-resolution population layer before estimating residents in the footprint.",
            "Confirm asset coverage locally before interpreting empty source results as operational absence.",
        ],
        "limitations": [
            "Overlap represents potential exposure to radar candidates, not damage.",
            "Census totals and density are block context. Their coarse support cannot locate residents.",
            "When available, raster estimates assume uniform population within each input cell.",
            "Zero mapped overlaps describe the queried sources only.",
            "Review priority is threshold stability, not validated hazard likelihood or consequence.",
        ],
    }
    for key, result_key in (("roads", "mapped_road_overlap_m"), ("buildings", "mapped_buildings_intersecting")):
        if source_meta.get(key, {}).get("status") == "NOT_PROVIDED":
            report[result_key] = None
            report["mapped_assets_in_valid_grid"][key] = None
    report["data_gaps"] = [kind for kind in ("population", "roads", "buildings")
                           if source_meta.get(kind, {}).get("status") == "NOT_PROVIDED"]
    # Census tabulation-block polygons are context, NOT spatial population exposure.
    # Never mark the population stage complete when its spatial count raster is missing.
    if population["estimated_residents"] is None and "population" not in report["data_gaps"]:
        report["data_gaps"].append("population_exposure")
    write_json(output / "impact-report.json", report)
    write_json(output / "impact-layers.geojson", feature_collection(output_features))
    write_json(output / "review-priority.geojson", feature_collection(zones))
    return report
