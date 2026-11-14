import numpy as np
import pytest

from phase2.detection import Settings, compare, metrics, screen
from phase2.run_m2 import controlled_benchmark


def test_same_sign_filter_keeps_clusters_and_preserves_mask():
    score = np.zeros((16, 16), dtype=np.float32)
    score[1:4, 1:4] = -6
    score[8:11, 8:11] = 6
    score[0, 8] = 8
    score[6, 6] = np.nan
    score[12, 12:15] = -8
    score[13, 12:15] = 8
    result = compare(score, Settings(min_pixels=5))
    assert np.all(result["adaptive"][1:4, 1:4] == 1)
    assert np.all(result["adaptive"][8:11, 8:11] == 2)
    assert np.all(result["adaptive"][12:14, 12:15] == 0)
    assert result["baseline"][0, 8] == 2
    assert result["adaptive"][0, 8] == 0
    assert result["adaptive"][6, 6] == 255
    assert np.isnan(result["stability"][6, 6])
    assert np.nanmin(result["stability"]) >= 1 / 3
    assert np.nanmax(result["stability"]) <= 1


def test_stability_flags_threshold_sensitive_cluster():
    score = np.zeros((12, 12), dtype=np.float32)
    score[3:6, 3:6] = 3.1
    result = compare(score)
    assert result["adaptive"][4, 4] == 2
    assert result["stability"][4, 4] == pytest.approx(2 / 3)
    assert result["uncertainty"][4, 4] == pytest.approx(1 / 3)


def test_does_not_fill_nodata_or_unchanged_hole():
    score = np.full((6, 6), 6.0)
    score[2, 2] = np.nan
    score[4, 4] = 0.0
    result = screen(score, 3, np.isfinite(score), 9)
    assert result[2, 2] == 255
    assert result[4, 4] == 0


def test_benchmark_is_labeled_and_detects_seeded_changes():
    result = controlled_benchmark(np.ones((80, 90), dtype=bool), Settings())
    assert result["status"] == "CONTROLLED_SIMULATION_ONLY"
    assert result["adaptive"]["tp"] == 288
    assert result["adaptive"]["fp"] < result["fixed_threshold"]["fp"]


def test_reference_metrics_ignore_unlabeled_and_invalid():
    truth = np.array([[0, 1, 255, 0, 1, 1]], dtype=np.uint8)
    pred = np.array([[0, 2, 1, 1, 255, 0]], dtype=np.uint8)
    result = metrics(truth, pred)
    assert [result[key] for key in ("tp", "fp", "tn", "fn")] == [1, 1, 1, 1]
    assert result["iou"] == pytest.approx(1 / 3)


def test_insufficient_support_fails_closed():
    with pytest.raises(ValueError, match="16 valid"):
        compare(np.full((10, 10), np.nan))
