"""M1 pair harmonization and independent-window translation diagnostics."""

import json

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy.ndimage import gaussian_filter, shift
from skimage.registration import phase_cross_correlation

from .integrity import safe
from .run_m2 import MAX_PIXELS, write_json

MASK_FIELDS = ("valid_mask_file", "layover_shadow_mask_file")


def scene_files(manifest):
    return {
        name
        for side in ("before", "after")
        for name in (
            *manifest[side]["raster_files"].values(),
            *(manifest[side][key] for key in MASK_FIELDS if manifest[side].get(key)),
        )
    }


def read_scene(root, scene, pol):
    with rasterio.open(safe(root, scene["raster_files"][pol])) as src:
        if (
            src.count != 1
            or src.driver != "GTiff"
            or src.dtypes[0] != "float32"
            or src.crs is None
            or not src.crs.is_projected
            or src.width * src.height > MAX_PIXELS
        ):
            raise ValueError("Expected a single-band projected float32 GeoTIFF AOI")
        power = src.read(1)
        valid = (src.read_masks(1) > 0) & np.isfinite(power) & (power > 0)
        grid = (src.crs, src.transform, src.shape)
        for key in MASK_FIELDS:
            if key not in scene or not scene[key]:
                if key == "valid_mask_file":
                    raise ValueError("Missing source validity mask")
                continue
            with rasterio.open(safe(root, scene[key])) as mask:
                if (
                    mask.count != 1
                    or mask.dtypes[0] != "uint8"
                    or (mask.crs, mask.transform, mask.shape) != grid
                ):
                    raise ValueError("Invalid source quality mask grid or type")
                flags = mask.read(1)
                if not np.isin(flags, [0, 1]).all():
                    raise ValueError("Quality mask values must be binary")
                valid &= flags == (1 if key == "valid_mask_file" else 0)
    return power, valid, grid


def regrid(power, valid, source, target):
    if source == target:
        return np.where(valid, power, np.nan), valid
    values = np.zeros(target[2], dtype=np.float32)
    support = np.zeros_like(values)
    for src, dst in (
        (np.where(valid, power, 0), values),
        (valid.astype("float32"), support),
    ):
        reproject(
            src,
            dst,
            src_transform=source[1],
            src_crs=source[0],
            dst_transform=target[1],
            dst_crs=target[0],
            resampling=Resampling.bilinear,
        )
    usable = (support >= 0.999) & np.isfinite(values) & (values > 0)
    return np.where(usable, values / np.maximum(support, 1e-6), np.nan), usable


def patches(before, after, valid):
    side = min(64, min(before.shape) // 3)
    if side < 24:
        return []
    taper = np.outer(np.hanning(side), np.hanning(side))
    results = []
    for row in range(0, before.shape[0] - side + 1, side):
        for col in range(0, before.shape[1] - side + 1, side):
            region = np.s_[row : row + side, col : col + side]
            if not valid[region].all():
                continue
            features = []
            for image in (before, after):
                raw = np.log(image[region]).astype("float64")
                highpass = raw - gaussian_filter(raw, 1.6)
                features.append(highpass * taper)
            a, b = features
            denom = np.linalg.norm(a) * np.linalg.norm(b)
            if denom < 1e-8:
                continue
            displacement, _, _ = phase_cross_correlation(
                a, b, upsample_factor=20, normalization=None
            )
            aligned = shift(b, displacement, order=1, mode="constant")
            aligned_norm = np.linalg.norm(a) * np.linalg.norm(aligned)
            similarity = float(np.sum(a * aligned) / aligned_norm) if aligned_norm else 0.0
            if similarity >= 0.35 and np.linalg.norm(displacement) <= 3:
                results.append(
                    {
                        "row": row,
                        "col": col,
                        "shift_rc": displacement.tolist(),
                        "similarity": similarity,
                        "fit": (row // side + col // side) % 2 == 0,
                    }
                )
    return results


def estimate(samples):
    fit = [s["shift_rc"] for s in samples if s["fit"]]
    holdout = [s["shift_rc"] for s in samples if not s["fit"]]
    if min(len(fit), len(holdout)) < 3:
        return None, None
    estimate = np.median(fit, axis=0)
    if np.quantile(np.linalg.norm(np.asarray(fit) - estimate, axis=1), 0.9) > 0.5:
        return None, None
    return estimate, float(np.quantile(np.linalg.norm(holdout, axis=1), 0.9))


def alignment(before, after, bv, av):
    samples = patches(before, after, bv & av)
    estimate_rc, before_residual = estimate(samples)
    report = {
        "status": "INSUFFICIENT_INTERNAL_EVIDENCE",
        "applied_shift_rc": [0.0, 0.0],
        "independently_certified": False,
        "initial_samples": samples,
        "holdout_p90_residual_before_px": before_residual,
        "holdout_p90_residual_after_px": before_residual,
    }
    if estimate_rc is None:
        return after, av, report
    report["estimated_shift_rc"] = estimate_rc.tolist()
    if np.linalg.norm(estimate_rc) < 0.2:
        report["status"] = "SMALL_ESTIMATED_SHIFT_NO_CORRECTION"
        return after, av, report
    moved = shift(np.where(av, after, 0), estimate_rc, order=1, mode="constant")
    support = shift(av.astype("float32"), estimate_rc, order=1, mode="constant") >= 0.999
    # Compare independent patches at the same locations that remain usable after the shift.
    verified = patches(before, moved, bv & support)
    original_holdout = {(s["row"], s["col"]): s["shift_rc"] for s in samples if not s["fit"]}
    pairs = [
        (original_holdout[(s["row"], s["col"])], s["shift_rc"])
        for s in verified
        if not s["fit"] and (s["row"], s["col"]) in original_holdout
    ]
    report["paired_holdout_windows"] = len(pairs)
    if len(pairs) >= 3:
        original, new = np.asarray(pairs).transpose(1, 0, 2)
        old_p90, new_p90 = [
            float(np.quantile(np.linalg.norm(x, axis=1), 0.9)) for x in (original, new)
        ]
        report["trial_holdout_p90_residual_px"] = new_p90
        if new_p90 <= 0.5 and old_p90 - new_p90 >= 0.1:
            report.update(
                status="INTERNAL_HOLDOUT_IMPROVED",
                applied_shift_rc=estimate_rc.tolist(),
                holdout_p90_residual_before_px=old_p90,
                holdout_p90_residual_after_px=new_p90,
            )
            return np.where(support, moved, np.nan), support, report
    report["status"] = "CORRECTION_NOT_SUPPORTED_BY_HOLDOUT"
    return after, av, report


def harmonize(source, output, pol):
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest.get("units") != "linear_power" or pol not in manifest.get("polarizations", []):
        raise ValueError("M1 requires declared linear-power SAR and common polarization")
    before, bv, grid = read_scene(source, manifest["before"], pol)
    after, av, after_grid = read_scene(source, manifest["after"], pol)
    crs, transform, (height, width) = grid
    if (
        crs.linear_units.lower() not in {"metre", "meter", "metres", "meters"}
        or transform.a <= 0
        or transform.e >= 0
        or transform.b != 0
        or transform.d != 0
        or not np.isclose(transform.a, -transform.e, rtol=0, atol=1e-5)
    ):
        raise ValueError("Before grid must be north-up with square metric pixels")
    after, av = regrid(after, av, after_grid, grid)
    after, av, report = alignment(before, after, bv, av)
    overlap = bv & av
    if np.count_nonzero(overlap) < 16:
        raise ValueError("Insufficient joint valid SAR support")
    difference_db = 10 * np.log10(after[overlap] / before[overlap])
    median_db = float(np.median(difference_db))
    report["measurement_reliability"] = {
        "joint_coverage_fraction": float(overlap.mean()),
        "median_log_ratio_db": median_db,
        "robust_log_ratio_scale_db": float(1.4826 * np.median(np.abs(difference_db - median_db))),
        "log_ratio_p05_p95_db": np.quantile(difference_db, [0.05, 0.95]).tolist(),
        "terrain_masks_supplied": {side: bool(manifest[side].get("layover_shadow_mask_file")) for side in ("before", "after")},
        "interpretation": "Scene diagnostics only; radiometric offsets can reflect real change or processing differences",
    }
    output.mkdir()
    for role, values, valid in (("before", before, bv), ("after", after, av)):
        scene = manifest[role]
        scene["raster_files"] = {pol: f"{role}_{pol}.tif"}
        scene["valid_mask_file"] = f"{role}_valid.tif"
        scene.pop("layover_shadow_mask_file", None)
        for name, data, nodata in (
            (
                scene["raster_files"][pol],
                np.where(valid, values, -9999).astype("float32"),
                -9999,
            ),
            (scene["valid_mask_file"], valid.astype("uint8"), None),
        ):
            with rasterio.open(
                output / name,
                "w",
                driver="GTiff",
                count=1,
                dtype=data.dtype,
                width=width,
                height=height,
                crs=crs,
                transform=transform,
                nodata=nodata,
                compress="deflate",
            ) as dst:
                dst.write(data, 1)
    with rasterio.open(
        output / "joint_quality_mask.tif",
        "w",
        driver="GTiff",
        count=1,
        dtype="uint8",
        width=width,
        height=height,
        crs=crs,
        transform=transform,
        compress="deflate",
    ) as dst:
        dst.write(overlap.astype("uint8"), 1)
    manifest["polarizations"] = [pol]
    manifest["grid"] = {
        "crs": str(crs),
        "pixel_size_m": transform.a,
        "width": width,
        "height": height,
    }
    manifest["processing_software"] += " + Phase 2 M1"
    manifest.setdefault("data_limitations", []).append(
        "M1 masks include input validity and any supplied terrain flags; internal diagnostics are not independent registration certification."
    )
    write_json(output / "manifest.json", manifest)
    report.update(
        joint_valid=int(overlap.sum()),
        total_pixels=overlap.size,
        crs=str(crs),
        after_regridded=after_grid != grid,
        scientific_approval=False,
        processing_identifiers={
            side: manifest[side].get("processing_identifier") for side in ("before", "after")
        },
    )
    write_json(output / "quality-report.json", report)
    return report
