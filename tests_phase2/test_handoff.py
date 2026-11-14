import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import rasterio

from phase2.run_m2 import run, sha256
from phase2.verify import verify


@pytest.fixture
def supplied_pair(tmp_path):
    source = Path(__file__).resolve().parents[1] / "data/nisar"
    return shutil.copytree(source, tmp_path / "pair")


def test_real_pair_is_exploratory_and_hashes_detect_tamper(supplied_pair, tmp_path):
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="allow-exploratory"):
        run(supplied_pair, output, polarization="HHHH")
    assert not output.exists()
    report = run(supplied_pair, output, polarization="HHHH", allow_exploratory=True)
    assert report["scientific_approval"] is False
    assert report["independent_evaluation"]["status"] == "BLOCKED_NO_INDEPENDENT_LABELS"
    assert (
        report["counts"]["baseline"]["decrease"] + report["counts"]["baseline"]["increase"] == 1233
    )
    result = verify(output, supplied_pair)
    assert result["artifacts_verified"] == 9
    with rasterio.open(output / "adaptive_change_mask.tif") as ds:
        assert set(np.unique(ds.read(1))) <= {0, 1, 2, 255}
        assert ds.nodata == 255
        assert (ds.width, ds.height) == (293, 303)
        assert ds.crs.to_epsg() == 3413
    (output / "evaluation-report.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact mismatch"):
        verify(output, supplied_pair)


def test_reference_checks_provenance_and_grid(supplied_pair, tmp_path):
    reference = tmp_path / "reference.tif"
    meta = tmp_path / "provenance.json"
    with rasterio.open(supplied_pair / "before_HHHH.tif") as src:
        profile = src.profile.copy()
        profile.update(dtype="uint8", nodata=255, predictor=1)
        labels = np.full(src.shape, 255, dtype=np.uint8)
        labels[:20, :20] = 0
        labels[20:40, :20] = 1
        with rasterio.open(reference, "w", **profile) as out:
            out.write(labels, 1)
    evidence = {
        "source": "software test labels",
        "label_definition": "test labels, no real event attribution",
        "labeling_method": "fixed disjoint squares created independently of predictions",
        "pair_id": "NISAR_GCOV_073_055_20261017_20261029_REAL",
        "sha256": sha256(reference),
        "independent_of_predictions": False,
    }
    meta.write_text(json.dumps(evidence))
    args = {
        "polarization": "HHHH",
        "allow_exploratory": True,
        "reference": reference,
        "reference_metadata": meta,
    }
    with pytest.raises(ValueError, match="attest independence"):
        run(supplied_pair, tmp_path / "bad", **args)
    assert not (tmp_path / "bad").exists()
    evidence["independent_of_predictions"] = True
    meta.write_text(json.dumps(evidence))
    report = run(supplied_pair, tmp_path / "good", **args)
    assert report["independent_evaluation"]["adaptive"]["labeled_valid_pixels"] == 800
    assert report["scientific_approval"] is False


def test_rejects_mismatched_grid(supplied_pair, tmp_path):
    with rasterio.open(supplied_pair / "after_HHHH.tif", "r+") as after:
        after.transform = after.transform * after.transform.translation(1, 0)
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="mismatched grid"):
        run(supplied_pair, output, polarization="HHHH", allow_exploratory=True)
    assert not output.exists()


def test_m3_export_preserves_occupied_area_and_flags(supplied_pair, tmp_path):
    from shapely.geometry import shape

    from phase2.export_candidates import export

    run_dir = tmp_path / "run"
    run(supplied_pair, run_dir, polarization="HHHH", allow_exploratory=True)
    output = tmp_path / "candidate.geojson"
    assert export(run_dir, supplied_pair, output)["status"] == "EXPLORATORY_FOOTPRINT_EXPORTED"
    feature = json.loads(output.read_text())
    assert shape(feature["geometry"]).is_valid
    assert feature["properties"]["scientific_approval"] is False
    with rasterio.open(run_dir / "adaptive_change_mask.tif") as ds:
        pixels = np.count_nonzero(np.isin(ds.read(1), [1, 2]))
        assert feature["properties"]["projected_grid_area_m2"] == pixels * 100
    (run_dir / "adaptive_change_mask.tif").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifact mismatch"):
        export(run_dir, supplied_pair, tmp_path / "bad.geojson")
