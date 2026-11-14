"""Export locally verified M2 candidates for M3's polygon input."""

import argparse
from pathlib import Path

import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from .run_m2 import sha256, write_json
from .verify import verify


def export(run, pair, out):
    run, out = Path(run).resolve(), Path(out).resolve()
    if out.exists() or out.is_relative_to(run):
        raise ValueError("Choose a new GeoJSON outside the M2 artifact directory")
    verification = verify(run, pair)
    mask = run / "adaptive_change_mask.tif"
    with rasterio.open(mask) as dataset:
        labels = dataset.read(1)
        candidates = (labels == 1) | (labels == 2)
        if not candidates.any():
            return {"status": "NO_CANDIDATES_AT_NOMINAL_SETTINGS"}
        # Four-way polygon connectivity preserves the occupied cells and avoids self-touching rings.
        polygons = [
            shape(geom)
            for geom, _ in shapes(
                candidates.astype("uint8"),
                mask=candidates,
                transform=dataset.transform,
                connectivity=4,
            )
        ]
        projected = unary_union(polygons)
        area = int(candidates.sum()) * abs(dataset.transform.determinant)
        if not projected.is_valid or abs(projected.area - area) > 1e-4:
            raise ValueError("Invalid geometry or pixel-to-polygon area mismatch")
        geometry = transform_geom(dataset.crs, "EPSG:4326", mapping(projected))
        if not shape(geometry).is_valid:
            raise ValueError("Candidate footprint invalid after reprojection")
    write_json(
        out,
        {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "pair_id": verification["pair_id"],
                "hazard_type": "unknown",
                "evidence_status": "UNVERIFIED",
                "scientific_approval": False,
                "registration_subpixel_certified": False,
                "candidate_pixels": int(candidates.sum()),
                "projected_grid_area_m2": area,
                "candidate_mask_sha256": sha256(mask),
                "m2_handoff_sha256": sha256(run / "m2-handoff.json"),
            },
        },
    )
    return {"status": "EXPLORATORY_FOOTPRINT_EXPORTED", "polygons": len(polygons)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--pair", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(export(args.run, args.pair, args.out))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"M3 candidate export: {exc}\n")


if __name__ == "__main__":
    main()
