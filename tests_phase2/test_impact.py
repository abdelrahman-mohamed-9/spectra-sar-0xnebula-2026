import json
import shutil

from pyproj import Transformer
from shapely.geometry import LineString, mapping, shape

from phase2.impact import assess
from phase2.jobs import CATALOG
from phase2.run_m2 import run


def test_positive_asset_overlap_and_census_context(tmp_path):
    pair = CATALOG / "data/nisar"
    m2 = tmp_path / "m2"
    run(pair, m2, polarization="HHHH", allow_exploratory=True)
    source = shutil.copytree(CATALOG / "data/geography", tmp_path / "geography")
    initial = tmp_path / "initial"
    assess(m2, source, initial)
    coverage = json.loads((initial / "review-priority.geojson").read_text())
    candidate = shape(coverage["features"][0]["geometry"])
    to_metric = Transformer.from_crs(4326, 3338, always_xy=True)
    to_geo = Transformer.from_crs(3338, 4326, always_xy=True)
    from shapely import transform as transform_shape

    point = transform_shape(
        candidate, to_metric.transform, interleaved=False
    ).representative_point()
    road = LineString([(point.x - 20, point.y), (point.x + 20, point.y)])
    for filename, geometry in (("buildings.geojson", point.buffer(2)), ("roads-8.geojson", road)):
        feature = {
            "type": "Feature",
            "geometry": mapping(transform_shape(geometry, to_geo.transform, interleaved=False)),
            "properties": {"OBJECTID": 1},
        }
        (source / filename).write_text(
            json.dumps({"type": "FeatureCollection", "features": [feature]})
        )
    report = assess(m2, source, tmp_path / "test")
    assert report["mapped_buildings_intersecting"] == 1
    assert report["mapped_road_overlap_m"] > 0
    assert report["estimated_residents_exposed"] is None
    assert "population_exposure" in report["data_gaps"]
    assert report["impact_confirmed"] is False


def test_population_raster_uses_coverage_and_cell_fractions(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box

    from phase2.impact import population_screen

    path = tmp_path / "population.tif"
    footprint = box(5, 0, 15, 10)
    profile = {
        "driver": "GTiff",
        "count": 1,
        "width": 2,
        "height": 1,
        "dtype": "float32",
        "crs": "EPSG:3338",
        "transform": from_origin(0, 10, 10, 10),
        "nodata": -1,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.array([[10, 6]], dtype="float32"), 1)
    assert population_screen(path, footprint)["estimated_residents"] == 8
    with rasterio.open(path, "r+") as dst:
        dst.write(np.array([[10, -1]], dtype="float32"), 1)
    incomplete = population_screen(path, footprint)
    assert incomplete["coverage_fraction"] == 0.5
    assert incomplete["estimated_residents"] is None
