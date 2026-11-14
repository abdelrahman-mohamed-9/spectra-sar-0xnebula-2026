"""Compare a fixed dB threshold with robust, spatially screened change detection."""

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class Settings:
    threshold_db: float = 3.0
    robust_sigma: float = 4.0
    min_pixels: int = 9
    sensitivity: float = 0.2

    def __post_init__(self):
        if not np.isfinite(self.threshold_db) or self.threshold_db <= 0:
            raise ValueError("threshold_db must be positive and finite")
        if not np.isfinite(self.robust_sigma) or self.robust_sigma <= 0:
            raise ValueError("robust_sigma must be positive and finite")
        if type(self.min_pixels) is not int or self.min_pixels <= 0:
            raise ValueError("min_pixels must be a positive integer")
        if not 0 < self.sensitivity < 1:
            raise ValueError("sensitivity must be between zero and one")


DEFAULT_SETTINGS = Settings()


def classify(score, threshold):
    valid = np.isfinite(score)
    labels = np.full(score.shape, 255, dtype=np.uint8)
    labels[valid] = 0
    labels[valid & (score <= -threshold)] = 1
    labels[valid & (score >= threshold)] = 2
    return labels


def screen(score, threshold, support, min_pixels):
    """Filter each direction separately, without filling holes or nodata."""
    raw = classify(score, threshold)
    screened = raw.copy()
    kernel = np.ones((3, 3), dtype=bool)
    for direction in (1, 2):
        components, _ = ndimage.label((raw == direction) & support, structure=kernel)
        sizes = np.bincount(components.ravel())
        keep = (components != 0) & (sizes[components] >= min_pixels)
        screened[(raw == direction) & ~keep] = 0
    return screened


def compare(score, settings=DEFAULT_SETTINGS):
    """Return signed masks and threshold stability. Stability is not a probability."""
    if score.ndim != 2:
        raise ValueError("Expected a two-dimensional score")
    valid = np.isfinite(score)
    if np.count_nonzero(valid) < 16:
        raise ValueError("At least 16 valid pixels are required for a robust estimate")
    values = score[valid]
    center = float(np.median(values))
    sigma = float(1.4826 * np.median(np.abs(values - center)))
    threshold = max(settings.threshold_db, settings.robust_sigma * sigma)
    centered = score - center
    available = ndimage.convolve(
        np.ones(score.shape, dtype=np.uint8),
        np.ones((3, 3), dtype=np.uint8),
        mode="constant",
    )
    neighbors = ndimage.convolve(
        valid.astype(np.uint8),
        np.ones((3, 3), dtype=np.uint8),
        mode="constant",
    )
    support = valid & (neighbors * 2 >= available)
    adaptive = screen(centered, threshold, support, settings.min_pixels)
    lower = screen(centered, threshold * (1 - settings.sensitivity), support, settings.min_pixels)
    higher = screen(centered, threshold * (1 + settings.sensitivity), support, settings.min_pixels)
    agreement = ((lower == adaptive).astype(np.float32) + 1 + (higher == adaptive)) / 3
    agreement[valid & ~support] = 1 / 3
    agreement[~valid] = np.nan
    review = screen(score, settings.threshold_db, support, settings.min_pixels)
    review_low = screen(score, settings.threshold_db * (1-settings.sensitivity), support, settings.min_pixels)
    review_high = screen(score, settings.threshold_db * (1+settings.sensitivity), support, settings.min_pixels)
    review_stability = ((review_low == review).astype(np.float32) + 1 + (review_high == review)) / 3
    review_stability[valid & ~support] = 1/3
    review_stability[~valid] = np.nan
    return {
        "review": review,
        "review_stability": review_stability,
        "baseline": classify(score, settings.threshold_db),
        "adaptive": adaptive,
        "stability": agreement,
        "uncertainty": 1 - agreement,
        "support": support,
        "center_db": center,
        "robust_scale_db": sigma,
        "adaptive_threshold_db": threshold,
    }


def counts(labels):
    return {
        name: int(np.count_nonzero(labels == code))
        for name, code in (
            ("unchanged", 0),
            ("decrease", 1),
            ("increase", 2),
            ("nodata", 255),
        )
    }


def metrics(truth, prediction):
    """Binary changed/unchanged agreement on labeled and valid pixels only."""
    valid = (truth != 255) & (prediction != 255)
    ref = truth[valid] == 1
    pred = prediction[valid] != 0
    tp = int(np.count_nonzero(ref & pred))
    fp = int(np.count_nonzero(~ref & pred))
    tn = int(np.count_nonzero(~ref & ~pred))
    fn = int(np.count_nonzero(ref & ~pred))

    def ratio(num, den):
        return num / den if den else None

    return {
        "labeled_valid_pixels": tp + fp + tn + fn,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "iou": ratio(tp, tp + fp + fn),
        "false_positive_rate": ratio(fp, fp + tn),
    }
