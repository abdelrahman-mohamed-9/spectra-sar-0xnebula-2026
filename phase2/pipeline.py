"""M1 to M4 execution over pinned local source snapshots."""

import json
import shutil

from . import benchmark, impact, m1, phase3
from .integrity import inventory, safe, verify_inventory
from .run_m2 import run as detect
from .run_m2 import write_json
from .verify import verify


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def execute(dataset, catalog_root, root, candidate_mode="conservative"):
    if candidate_mode not in {"conservative", "review"}:
        raise ValueError("Unknown candidate mode")
    root.mkdir(exist_ok=False)
    sources = catalog_root / "data"
    pinned = load(catalog_root / "catalog.json")[dataset]
    snapshot = root / "sources"
    snapshot.mkdir()
    verify_inventory(sources, pinned)
    for name in pinned:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe(sources, name), target)
    verify_inventory(snapshot, pinned)
    pair = snapshot / "nisar"
    original = load(pair / "manifest.json")
    if {"manifest.json", *m1.scene_files(original)} - {
        name.removeprefix("nisar/") for name in pinned if name.startswith("nisar/")
    }:
        raise ValueError("Unpinned source files in pair manifest")

    pol = original["polarizations"][0]
    source_receipt = load(pair / "input-provenance.json")["input_sha256"]
    for side in ("before", "after"):
        raster = original[side]["raster_files"][pol]
        if pinned[f"nisar/{raster}"]["sha256"] != source_receipt.get(side):
            raise ValueError("Supplied NISAR extract differs from its original import receipt")
    m1_dir = root / "M1"
    quality = m1.harmonize(pair, m1_dir, pol)
    m1_receipt = inventory(root, [f"M1/{p.name}" for p in m1_dir.iterdir()])
    verify_inventory(root, m1_receipt)
    m2_dir = root / "M2"
    reference = snapshot / "reference/labels.tif"
    ref_args = {"reference":reference,"reference_metadata":snapshot/"reference/provenance.json"} if reference.exists() else {}
    scientific = detect(m1_dir, m2_dir, polarization=pol, allow_exploratory=True, **ref_args)
    verify_inventory(root, m1_receipt)
    verified = verify(m2_dir, m1_dir)
    m2_receipt = inventory(root, [f"M2/{p.name}" for p in m2_dir.iterdir()])

    verify_inventory(snapshot, pinned)
    verify_inventory(root, m2_receipt)
    exposure = impact.assess(m2_dir, snapshot / "geography", root / "M3", candidate_mode)
    m3_receipt = inventory(root, [f"M3/{p.name}" for p in (root / "M3").iterdir()])
    advanced = phase3.assess(root, quality, candidate_mode)
    phase3_receipt = inventory(root, [f"Phase3/{p.name}" for p in (root / "Phase3").iterdir()])
    if (snapshot / "benchmark").is_dir():
        external = benchmark.benchmark(snapshot / "benchmark", root / "external-evaluation.json")
    else:
        external = {"status":"NOT_INCLUDED_FOR_IMPORTED_DATASET"}
        write_json(root / "external-evaluation.json", external)
    verify_inventory(snapshot, pinned)
    verify_inventory(root, {**m1_receipt, **m2_receipt, **m3_receipt})
    counts = scientific["counts"]["adaptive" if candidate_mode == "conservative" else "review"]
    report = {
        "status": "COMPLETED_EXPLORATORY",
        "scientific_approval": False,
        "pair_id": original["pair_id"],
        "phase3": advanced,
        "m1": {
            "status": quality["status"],
            "joint_valid": quality["joint_valid"],
            "estimated_shift_rc": quality.get("estimated_shift_rc"),
            "holdout_p90_residual_px": quality["holdout_p90_residual_after_px"],
            "independently_certified": False,
        },
        "m2": {
            "candidate_mode": candidate_mode,
            "conservative_pixels": sum(scientific["counts"]["adaptive"][k] for k in ("increase", "decrease")),
            "review_pixels": sum(scientific["counts"]["review"][k] for k in ("increase", "decrease")),
            "candidate_pixels": counts["increase"] + counts["decrease"],
            "pair_accuracy": scientific["independent_evaluation"]["status"],
            "alaska_accuracy": scientific["independent_evaluation"]["status"],
            "external_benchmark": external["status"],
        },
        "m3": {
            "status": exposure["status"],
            "candidate_area_m2": exposure["candidate_area_m2"],
            "data_gaps": exposure["data_gaps"],
            "estimated_residents_exposed": exposure["estimated_residents_exposed"],
            "mapped_road_overlap_m": exposure["mapped_road_overlap_m"],
            "mapped_buildings_intersecting": exposure["mapped_buildings_intersecting"],
        },
        "m4": {"status": "VERIFIED_AGAINST_LOCAL_CATALOG", "m2": verified},
        "acceptance_gaps": [
            "Independent calibration, geometric and radiometric verification; review any mixed processing versions",
            "Independent event labels and scientific review for this pair; user-supplied labels are not automatically certified",
            "Spatially resolved population and validated asset coverage for consequence estimates",
        ],
    }
    write_json(root / "summary.json", report)
    from .preview import render, report_markdown
    previews = render(root, original, candidate_mode)
    report_markdown(root, report, scientific, exposure, external)
    extras = ["external-evaluation.json", "summary.json", "REPORT.md", *previews]
    if (root/"external-ml-prediction.tif").exists(): extras.append("external-ml-prediction.tif")
    extra = inventory(root, extras)
    lineage = {
        "schema_version": "1.0",
        "status": "PASS_LOCAL_BYTES",
        "scientific_approval": False,
        "provider_authentication": "NOT_ESTABLISHED_FOR_ORIGINAL_NISAR_GRANULES",
        "local_import_receipt_verified": True,
        "source_scenes": [original[side] for side in ("before", "after")],
        "stages": {
            "Phase3": {"inputs": [*m1_receipt, *m2_receipt, *m3_receipt, *(f"sources/{key}" for key in pinned if key.startswith("geography/"))], "outputs": list(phase3_receipt)},
            "M1": {
                "inputs": [f"sources/{k}" for k in pinned if k.startswith("nisar/")],
                "outputs": list(m1_receipt),
            },
            "M2": {"inputs": list(m1_receipt), "outputs": list(m2_receipt)},
            "M3": {
                "inputs": [
                    *m2_receipt,
                    *(f"sources/{k}" for k in pinned if k.startswith("geography/")),
                ],
                "outputs": list(m3_receipt),
            },
            "external_benchmark": {
                "inputs": [
                    f"sources/{k}"
                    for k in pinned
                    if k.startswith("benchmark/") or k == "benchmark-source.json"
                ],
                "outputs": ["external-evaluation.json"],
            },
        },
        "files": {
            **{f"sources/{k}": v for k, v in pinned.items()},
            **m1_receipt,
            **m2_receipt,
            **m3_receipt,
            **phase3_receipt,
            **extra,
        },
    }
    verify_inventory(root, lineage["files"])
    ordered = {name: lineage["stages"][name] for name in ("M1", "M2", "M3", "Phase3", "external_benchmark")}
    phase3.evidence(root, lineage["files"], ordered)
    lineage["files"].update(inventory(root, ["Phase3/processing-log.json"]))
    write_json(root / "provenance.json", lineage)
    return report, {**lineage["files"], **inventory(root, ["provenance.json"])}
