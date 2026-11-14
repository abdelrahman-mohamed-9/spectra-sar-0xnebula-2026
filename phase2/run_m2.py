"""Phase 2 M2 entry point, working with the existing M1 manifest and GeoTIFFs."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
import scipy

from .detection import DEFAULT_SETTINGS, Settings, classify, compare, counts, metrics

NODATA = -9999.0
MAX_PIXELS = 2_000_000
STATUS = "EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def input_paths(pair, manifest, polarization, safe_pair_file):
    files = {"manifest.json": pair / "manifest.json"}
    for side in ("before", "after"):
        scene = manifest[side]
        names = [scene["raster_files"][polarization], scene["valid_mask_file"]]
        if scene.get("layover_shadow_mask_file"):
            names.append(scene["layover_shadow_mask_file"])
        for name in names:
            files[name] = safe_pair_file(pair, name)
    return files


def declared_file(pair, name):
    path = (pair / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(pair) or not path.is_file():
        raise ValueError(f"Missing or unsafe input: {name}")
    return path


def write_raster(path, array, grid, *, nodata, quantity):
    dtype = "uint8" if array.dtype == np.uint8 else "float32"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        count=1,
        dtype=dtype,
        nodata=nodata,
        compress="deflate",
        **grid,
    ) as dst:
        dst.write(np.where(np.isfinite(array), array, nodata).astype(dtype), 1)
        dst.update_tags(quantity=quantity, scientific_approval="false")
        if dtype == "uint8":
            dst.update_tags(classes="0:no_candidate;1:decrease;2:increase;255:nodata")


def read_score(pair, polarization, grid):
    from change_detector import log_ratio_db
    from data_loader import iter_pair_tiles

    score = np.full((grid["height"], grid["width"]), np.nan, dtype=np.float32)
    for tile in iter_pair_tiles(pair, polarization=polarization):
        rows, cols = tile.window.toslices()
        score[rows, cols] = log_ratio_db(tile.before, tile.after, tile.valid)
    return score


def evaluate_reference(path, metadata_path, manifest, grid, result):
    metadata_bytes = metadata_path.read_bytes()
    evidence = json.loads(metadata_bytes)
    if not isinstance(evidence, dict):
        raise TypeError("Reference provenance must be a JSON object")
    required = ("source", "label_definition", "labeling_method")
    if any(
        not isinstance(evidence.get(field), str) or not evidence[field].strip()
        for field in required
    ):
        raise ValueError(
            "Reference provenance requires source, label_definition and labeling_method"
        )
    if (
        evidence.get("independent_of_predictions") is not True
        or evidence.get("pair_id") != manifest["pair_id"]
        or evidence.get("sha256") != sha256(path)
    ):
        raise ValueError(
            "Reference provenance must attest independence and match pair ID and digest"
        )
    with rasterio.open(path) as ref:
        if (
            ref.count != 1
            or ref.dtypes[0] != "uint8"
            or ref.nodata != 255
            or any(getattr(ref, name) != value for name, value in grid.items())
        ):
            raise ValueError("Reference must be a matching one-band uint8 raster with nodata 255")
        values = ref.read(1, masked=True).filled(255)
    if not np.isin(values, [0, 1, 255]).all():
        raise ValueError("Reference codes must be 0 unchanged, 1 change, 255 unlabeled")
    valid = result["adaptive"] != 255
    if not np.any((values == 0) & valid) or not np.any((values == 1) & valid):
        raise ValueError("Reference needs both changed and unchanged labels on valid SAR pixels")
    if evidence["sha256"] != sha256(path):
        raise ValueError("Reference changed during evaluation")
    return {
        "status": "EVALUATED_USER_SUPPLIED_REFERENCE",
        "provenance": evidence,
        "provenance_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
        "baseline": metrics(values, result["baseline"]),
        "adaptive": metrics(values, result["adaptive"]),
        "review": metrics(values, result["review"]),
    }


def controlled_benchmark(valid, settings):
    """Inject known dB patterns on the supplied raster grid, with simulated noise."""
    h, w = valid.shape
    if min(h, w) < 36:
        return {"status": "SKIPPED_GRID_TOO_SMALL"}
    rng = np.random.default_rng(20261114)
    score = (0.8 + rng.normal(0, 0.65, size=valid.shape)).astype(np.float32)
    truth = np.zeros(valid.shape, dtype=np.uint8)
    patches = [(h // 4, w // 4, -6), (h // 2, w // 2, 6)]
    for row, col, delta in patches:
        score[row : row + 12, col : col + 12] += delta
        truth[row : row + 12, col : col + 12] = 1
    stable = np.argwhere(valid & (truth == 0))
    if not stable.size or not np.any(valid & (truth == 1)):
        return {"status": "SKIPPED_INSUFFICIENT_VALID_FIXTURE_LABELS"}
    chosen = stable[rng.choice(len(stable), min(len(stable), 100), replace=False)]
    score[tuple(chosen.T)] += rng.choice([-6, 6], len(chosen))
    score[~valid] = np.nan
    truth[~valid] = 255
    result = compare(score, settings)
    return {
        "status": "CONTROLLED_SIMULATION_ONLY",
        "seed": 20261114,
        "design": "Known signed 12×12 changes, 0.8 dB global offset, Gaussian noise (0.65 dB SD), and up to 100 impulse outliers",
        "fixed_threshold": metrics(truth, result["baseline"]),
        "adaptive": metrics(truth, result["adaptive"]),
    }


def run(
    pair,
    output,
    *,
    polarization,
    settings=DEFAULT_SETTINGS,
    allow_exploratory=False,
    reference=None,
    reference_metadata=None,
):
    # Reuse the existing M2 scripts on PYTHONPATH.
    from data_loader import load_manifest, safe_pair_file
    from filters import process_pair
    from input_validator import inspect_pair
    from pipeline import prepare_filtered_pair
    from registration import inspect_registration

    pair, output = Path(pair).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(pair) or pair.is_relative_to(output):
        raise ValueError("Choose a new output directory separate from the input tree")
    if bool(reference) != bool(reference_metadata):
        raise ValueError("Provide both the reference raster and its metadata")
    declared_file(pair, "manifest.json")
    manifest = load_manifest(pair)
    if polarization not in manifest.get("polarizations", ()):
        raise ValueError("Requested polarization is absent from the pair")
    paths = input_paths(pair, manifest, polarization, safe_pair_file)
    # Track GDAL sidecars as well as TIFF bytes. They may alter georeferencing or masks.
    for path in tuple(paths.values()):
        if path.suffix.lower() not in (".tif", ".tiff"):
            continue
        with rasterio.open(path) as dataset:
            for name in dataset.files:
                dependency = Path(name).resolve()
                if not dependency.is_relative_to(pair):
                    raise ValueError("Raster dependency escapes the pair directory")
                paths.setdefault(dependency.relative_to(pair).as_posix(), dependency)
    paths["manifest.json"] = declared_file(pair, "manifest.json")
    hashes = {name: sha256(path) for name, path in sorted(paths.items())}
    source = paths[manifest["before"]["raster_files"][polarization]]
    with rasterio.open(source) as src:
        grid = {key: getattr(src, key) for key in ("width", "height", "crs", "transform")}
        if src.width * src.height > MAX_PIXELS:
            raise ValueError(f"Use an M1 AOI crop of at most {MAX_PIXELS:,} pixels")
    qa = inspect_pair(pair)
    if qa["status"] == "REJECT":
        raise ValueError("M1 pair rejected: " + "; ".join(qa["errors"]))
    if not allow_exploratory:
        raise ValueError("This workflow requires --allow-exploratory pending scientific review")
    registration = inspect_registration(
        pair, polarization=polarization, allow_warning=True, patch=256
    )
    if registration["status"] == "REJECT":
        raise ValueError("Registration diagnostic rejected the pair")
    raw_score = read_score(pair, polarization, grid)
    with TemporaryDirectory(prefix="spectra-phase2-lee-") as scratch:
        filtered = Path(scratch) / "filtered"
        staged = Path(scratch) / "staged"
        process_pair(pair, filtered, polarization=polarization, allow_warning=True)
        prepare_filtered_pair(pair, filtered, staged, polarization)
        score = read_score(staged, polarization, grid)
    score[~np.isfinite(raw_score)] = np.nan
    result = compare(score, settings)
    raw_baseline = classify(np.where(np.isfinite(score), raw_score, np.nan), settings.threshold_db)
    validity = np.isfinite(score)
    candidate_counts = {
        key: counts(value)
        for key, value in (
            ("raw_baseline", raw_baseline),
            ("baseline", result["baseline"]),
            ("adaptive", result["adaptive"]),
            ("review", result["review"]),
        )
    }
    truth = (
        evaluate_reference(Path(reference), Path(reference_metadata), manifest, grid, result)
        if reference
        else {
            "status": "BLOCKED_NO_INDEPENDENT_LABELS",
            "baseline": None,
            "adaptive": None,
        }
    )
    benchmark = controlled_benchmark(validity, settings)
    if any(sha256(path) != hashes[name] for name, path in paths.items()):
        raise ValueError("Input changed during processing")
    if load_manifest(pair) != manifest:
        raise ValueError("Manifest changed during processing")

    report = {
        "pair_id": manifest["pair_id"],
        "polarization": polarization,
        "status": STATUS,
        "scientific_approval": False,
        "registration_subpixel_certified": False,
        "before": {
            k: manifest["before"].get(k)
            for k in ("scene_id", "acquired_utc", "collection", "processing_identifier")
        },
        "after": {
            k: manifest["after"].get(k)
            for k in ("scene_id", "acquired_utc", "collection", "processing_identifier")
        },
        "input_qa": qa,
        "registration": registration,
        "input_limitations": manifest.get("data_limitations", []),
        "methods": {
            "raw_baseline": "Unfiltered signed log ratio, fixed dB threshold, shared evaluation support",
            "baseline": "Phase 1 method: mask-aware Lee filtering (7×7, four assumed looks) and signed 10 log10(after/before) with a fixed dB threshold",
            "adaptive": "Scene median centering, median absolute deviation threshold with dB floor, same-sign connected components and valid-neighbor screening",
            "review": "Uncentered fixed dB floor with same-sign component screening; higher-sensitivity candidate review, not validated accuracy",
            "settings": asdict(settings),
            "center_db": result["center_db"],
            "robust_scale_db": result["robust_scale_db"],
            "adaptive_threshold_db": result["adaptive_threshold_db"],
        },
        "counts": candidate_counts,
        "grid_cell_area_m2": abs(grid["transform"].determinant),
        "candidate_area_km2_on_projected_grid": {
            key: (value["decrease"] + value["increase"]) * abs(grid["transform"].determinant) / 1e6
            for key, value in candidate_counts.items()
        },
        "adaptive_nominal_status": (
            "CANDIDATES_RETAINED"
            if np.any(np.isin(result["adaptive"], [1, 2]))
            else "NO_CANDIDATES_AT_NOMINAL_SETTINGS"
        ),
        "robust_threshold_stability": {
            "meaning": "Agreement with the nominal signed class across three threshold settings, downweighted for low valid-neighbor support",
            "not_calibrated_probability": True,
            "includes_registration_or_label_uncertainty": False,
            "adaptive_candidate_pixels_stable_at_all_thresholds": int(
                np.count_nonzero(np.isin(result["adaptive"], [1, 2]) & (result["stability"] == 1))
            ),
        },
        "independent_evaluation": truth,
        "controlled_benchmark": benchmark,
        "ml_status": "NOT_RUN_NO_APPROVED_TRAINING_AND_HELD_OUT_DATA",
        "limitations": [
            "The robust estimator assumes background dominates the AOI. Median centering may suppress widespread genuine changes.",
            "Small true changes may be removed by the component filter.",
            "Backscatter changes do not identify an event or confirm damage.",
            "Candidate counts are not measured false positives on this real pair.",
        ],
        "versions": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "rasterio": rasterio.__version__,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".m2-", dir=output.parent) as scratch:
        root = Path(scratch)
        rasters = {
            "review_change_mask": (result["review"], 255, "fixed threshold spatial review candidates"),
            "review_stability": (result["review_stability"], NODATA, "review threshold stability; not probability"),
            "signed_log_ratio_db": (score, NODATA, "signed SAR power log ratio in dB"),
            "raw_baseline_change_mask": (
                raw_baseline,
                255,
                "unfiltered fixed threshold candidates",
            ),
            "baseline_change_mask": (
                result["baseline"],
                255,
                "Lee-filtered fixed threshold candidates",
            ),
            "adaptive_change_mask": (
                result["adaptive"],
                255,
                "robust spatial candidate change",
            ),
            "confidence_stability": (
                result["stability"],
                NODATA,
                "threshold stability; not calibrated confidence",
            ),
            "uncertainty_sensitivity": (
                result["uncertainty"],
                NODATA,
                "one minus threshold stability",
            ),
        }
        for name, (array, nodata, quantity) in rasters.items():
            write_raster(root / f"{name}.tif", array, grid, nodata=nodata, quantity=quantity)
        write_json(root / "evaluation-report.json", report)
        files = {
            file.name: {"sha256": sha256(file), "bytes": file.stat().st_size}
            for file in sorted(root.iterdir())
            if file.is_file()
        }
        write_json(
            root / "m2-handoff.json",
            {
                "schema_version": "2.0",
                "pair_id": manifest["pair_id"],
                "polarization": polarization,
                "status": STATUS,
                "scientific_approval": False,
                "registration_subpixel_certified": False,
                "calibrated_confidence": False,
                "candidate_mask": "adaptive_change_mask.tif",
                "classes": {
                    "0": "no candidate",
                    "1": "decrease",
                    "2": "increase",
                    "255": "nodata",
                },
                "input_sha256": hashes,
                "artifacts": files,
            },
        )
        output.mkdir(exist_ok=False)
        for file in sorted(root.iterdir(), key=lambda item: item.name == "m2-handoff.json"):
            file.rename(output / file.name)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pair", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--polarization", default="HHHH")
    parser.add_argument("--threshold-db", type=float, default=3.0)
    parser.add_argument("--robust-sigma", type=float, default=4.0)
    parser.add_argument("--min-pixels", type=int, default=9)
    parser.add_argument("--allow-exploratory", action="store_true")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--reference-metadata", type=Path)
    args = parser.parse_args()
    try:
        report = run(
            args.pair,
            args.out,
            polarization=args.polarization,
            settings=Settings(args.threshold_db, args.robust_sigma, args.min_pixels),
            allow_exploratory=args.allow_exploratory,
            reference=args.reference,
            reference_metadata=args.reference_metadata,
        )
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        rasterio.errors.RasterioError,
    ) as exc:
        parser.exit(2, f"M2 Phase 2: {exc}\n")
    print(json.dumps({"status": report["status"], "counts": report["counts"]}))


if __name__ == "__main__":
    main()
