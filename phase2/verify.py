"""Verify locally recorded M2 bytes before downstream processing."""

import argparse
import json
from pathlib import Path

from .run_m2 import STATUS, declared_file, sha256

REQUIRED = {
    "review_change_mask.tif",
    "review_stability.tif",
    "signed_log_ratio_db.tif",
    "raw_baseline_change_mask.tif",
    "baseline_change_mask.tif",
    "adaptive_change_mask.tif",
    "confidence_stability.tif",
    "uncertainty_sensitivity.tif",
    "evaluation-report.json",
}


def verify(output, pair):
    output, pair = Path(output).resolve(), Path(pair).resolve()
    manifest = json.loads(declared_file(output, "m2-handoff.json").read_text(encoding="utf-8"))
    source = json.loads(declared_file(pair, "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != "2.0"
        or manifest.get("status") != STATUS
        or manifest.get("scientific_approval") is not False
        or manifest.get("registration_subpixel_certified") is not False
        or manifest.get("calibrated_confidence") is not False
        or manifest.get("candidate_mask") != "adaptive_change_mask.tif"
        or manifest.get("pair_id") != source.get("pair_id")
    ):
        raise ValueError("Invalid handoff metadata")
    files = manifest["artifacts"]
    if not REQUIRED <= files.keys():
        raise ValueError("Incomplete M2 handoff")
    for name, record in files.items():
        path = declared_file(output, name)
        if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise ValueError(f"M2 artifact mismatch: {name}")
    inputs = manifest["input_sha256"]
    required_inputs = {"manifest.json"}
    for side in ("before", "after"):
        scene = source[side]
        required_inputs.add(scene["valid_mask_file"])
        required_inputs.add(scene["raster_files"][manifest["polarization"]])
        if scene.get("layover_shadow_mask_file"):
            required_inputs.add(scene["layover_shadow_mask_file"])
    if not required_inputs <= inputs.keys():
        raise ValueError("Incomplete input receipt")
    for name, digest in inputs.items():
        if sha256(declared_file(pair, name)) != digest:
            raise ValueError(f"M1 input mismatch: {name}")
    return {
        "status": "PASS_LOCAL_BYTES",
        "pair_id": manifest["pair_id"],
        "artifacts_verified": len(files),
        "inputs_verified": len(inputs),
        "scientific_approval": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pair", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.output, args.pair)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"M2 verification: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
