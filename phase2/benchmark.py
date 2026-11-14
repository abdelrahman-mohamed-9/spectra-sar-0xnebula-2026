"""External Sentinel-1 flood-label benchmark, separate from Alaska NISAR."""

from pathlib import Path

import numpy as np
import rasterio
from scipy.optimize import minimize
from scipy.ndimage import uniform_filter
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

from .detection import DEFAULT_SETTINGS, compare, metrics
from .run_m2 import sha256, write_json

TRAIN = ("Ghana_103272", "USA_1010394")
HOLDOUT = "Spain_1167260"
SOURCE = "https://doi.org/10.5281/zenodo.7946594"


def chip(root):
    records = {}
    arrays = {}
    grid = None
    for role in ("before", "after", "labels"):
        path = root / f"{role}.tif"
        with rasterio.open(path) as ds:
            if grid is None:
                grid = ds.crs, ds.shape, np.asarray(tuple(ds.transform)[:6])
            if (ds.crs, ds.shape) != grid[:2] or not np.allclose(
                tuple(ds.transform)[:6],
                grid[2],
                rtol=0,
                atol=1e-10,
            ):
                raise ValueError("External benchmark grids differ")
            arrays[role] = ds.read(1, masked=True).astype("float64").filled(np.nan)
        records[path.name] = sha256(path)
    if not np.isin(arrays["labels"], [-1, 0, 1]).all():
        raise ValueError("Unexpected benchmark label codes")
    before, after = arrays["before"], arrays["after"]
    valid = np.isfinite(before) & np.isfinite(after)
    truth = np.where(valid & (arrays["labels"] >= 0), arrays["labels"], 255).astype("uint8")
    score = np.where(valid, after - before, np.nan)
    features = np.stack([after, score, before], axis=-1)
    return features, truth, score, records


def fit_logistic(x, y):
    mean, scale = x.mean(axis=0), x.std(axis=0)
    if not np.all(scale > 0) or set(np.unique(y)) != {0, 1}:
        raise ValueError("Training features need variance and both label classes")
    design = np.column_stack((np.ones(len(x)), (x - mean) / scale))

    def objective(weights):
        value = design @ weights
        loss = np.logaddexp(0, value) - y * value
        return float(loss.mean() + 0.01 * (weights[1:] @ weights[1:]))

    result = minimize(objective, np.zeros(design.shape[1]), method="BFGS")
    if not result.success or not np.isfinite(result.x).all():
        raise ValueError("Logistic baseline did not converge")
    return mean, scale, result.x



def spatial_features(x):
    """Image-only local statistics; no reference labels enter feature construction."""
    valid = np.isfinite(x).all(axis=-1)
    weight = uniform_filter(valid.astype(float), size=5, mode="constant")
    features = [x[..., i] for i in range(3)]
    for index in (0, 1):
        band = np.where(valid, x[..., index], 0)
        mean = uniform_filter(band, size=5, mode="constant") / np.maximum(weight, 1e-12)
        variance = uniform_filter(band * band, size=5, mode="constant") / np.maximum(weight, 1e-12) - mean * mean
        features.extend((mean, np.sqrt(np.maximum(variance, 0))))
    return np.stack(features, axis=-1)


def train_sample(x, y, seed):
    indices = np.flatnonzero((y != 255) & np.isfinite(x).all(axis=-1))
    rng = np.random.default_rng(seed)
    indices = rng.choice(indices, min(30000, len(indices)), replace=False)
    return x.reshape(-1, x.shape[-1])[indices], y.ravel()[indices]


def new_model():
    return HistGradientBoostingClassifier(max_iter=80, max_leaf_nodes=15,
        min_samples_leaf=30, l2_regularization=1, early_stopping=False, random_state=24)


def tuned_comparator(root, holdout_x, holdout_truth):
    """Select threshold using only country-separated out-of-fold TRAIN predictions."""
    training = []
    for i, name in enumerate(TRAIN):
        x, y, _, _ = chip(root / name)
        training.append(train_sample(spatial_features(x), y, 100 + i))
    validation = []
    fold_reports = []
    with threadpool_limits(limits=2):
        for i in range(len(training)):
            fit_x, fit_y = training[1-i]
            val_x, val_y = training[i]
            model = new_model().fit(fit_x, fit_y)
            scores = model.predict_proba(val_x)[:, 1]
            validation.append((val_y, scores))
            fold_reports.append({"trained_on": TRAIN[1-i], "validated_on": TRAIN[i], "pixels": len(val_y)})
        curve = []
        for threshold in np.linspace(.05, .95, 19):
            fold_f1 = [metrics(y, (scores >= threshold).astype('uint8'))['f1'] or 0
                       for y, scores in validation]
            curve.append({"threshold": float(threshold), "mean_country_f1": float(np.mean(fold_f1))})
        best = max(curve, key=lambda row: (row['mean_country_f1'], -abs(row['threshold']-.5)))
        model = new_model().fit(np.concatenate([v[0] for v in training]),
                                np.concatenate([v[1] for v in training]))
        x = spatial_features(holdout_x)
        valid = np.isfinite(x).all(axis=-1)
        pred = np.full(holdout_truth.shape, 255, dtype='uint8')
        pred[valid] = (model.predict_proba(x[valid])[:, 1] >= best['threshold']).astype('uint8')
    return pred, {
        "algorithm": "HistGradientBoostingClassifier",
        "hyperparameters": new_model().get_params(),
        "feature_order": ["after_vv_db", "delta_vv_db", "before_vv_db", "after_mean5", "after_sd5", "delta_mean5", "delta_sd5"],
        "threshold": best['threshold'], "threshold_objective": "Mean country F1 on TRAIN-only out-of-fold predictions",
        "validation_folds": fold_reports, "threshold_curve": curve,
        "test_labels_used_for_selection": False,
        "training_pixels": int(sum(len(v[1]) for v in training)),
        "limitations": ["Only two training chips and one held-out test chip; no claim of broad generalization.",
            "These water/flood labels do not validate generic change or Alaska NISAR.",
            "Probabilities are not calibrated event or damage probabilities."]}


def recall_threshold(root):
    """TRAIN-only country cross-validation; F2 gives recall more weight than precision."""
    folds=[]
    for i, name in enumerate(TRAIN):
        tx, ty, _, _ = chip(root / TRAIN[1-i])
        rng=np.random.default_rng(20261114+i)
        indices=[]
        for label in (0,1):
            candidates=np.flatnonzero(ty==label)
            indices.extend(rng.choice(candidates,min(5000,len(candidates)),replace=False))
        indices=np.asarray(indices)
        mean, scale, weights=fit_logistic(tx.reshape(-1,3)[indices],ty.ravel()[indices])
        vx, vy, _, _=chip(root/name)
        valid=vy!=255
        scores=weights[0]+((vx[valid]-mean)/scale)@weights[1:]
        folds.append((vy[valid],scores))
    curve=[]
    for threshold in np.linspace(-4,4,41):
        f2=[]
        for truth,scores in folds:
            m=metrics(truth,(scores>=threshold).astype('uint8'))
            den=5*m['tp']+4*m['fn']+m['fp']
            f2.append(5*m['tp']/den if den else 0)
        curve.append({'logit_threshold':float(threshold),'mean_country_f2':float(np.mean(f2))})
    chosen=max(curve,key=lambda row:(row['mean_country_f2'],-abs(row['logit_threshold'])))
    return {'objective':'Mean country F2 on TRAIN-only out-of-fold predictions',
        'threshold':chosen['logit_threshold'],'curve':curve,'test_labels_used_for_selection':False,
        'validation_countries':list(TRAIN),
        'interpretation':'Recall-oriented external comparator, not calibrated event probability or Alaska inference'}


def benchmark(root, output):
    root = Path(root)
    rng = np.random.default_rng(20261114)
    features, targets, sources = [], [], {}
    for name in TRAIN:
        x, y, _, sources[name] = chip(root / name)
        for label in (0, 1):
            candidates = np.flatnonzero(y == label)
            selected = rng.choice(candidates, min(len(candidates), 5000), replace=False)
            features.append(x.reshape(-1, x.shape[-1])[selected])
            targets.append(y.ravel()[selected])
    mean, scale, weights = fit_logistic(np.concatenate(features), np.concatenate(targets))
    x, truth, score, sources[HOLDOUT] = chip(root / HOLDOUT)
    valid = np.isfinite(score)
    logit = np.full(truth.shape, np.nan)
    logit[valid] = weights[0] + ((x[valid] - mean) / scale) @ weights[1:]
    recall_policy = recall_threshold(root)
    rule = compare(score, DEFAULT_SETTINGS)
    predictions = {
        "fixed_darkening": np.where(valid, rule["baseline"] == 1, 255).astype("uint8"),
        "robust_darkening": np.where(valid, rule["adaptive"] == 1, 255).astype("uint8"),
        "logistic_baseline": np.where(valid, logit >= 0, 255).astype("uint8"),
        "logistic_train_f2_policy": np.where(valid, logit >= recall_policy["threshold"], 255).astype("uint8"),
    }
    tuned, training_report = tuned_comparator(root, x, truth)
    predictions["spatial_ml_tuned"] = tuned
    with rasterio.open(root / HOLDOUT / "labels.tif") as ref:
        profile = ref.profile.copy()
        profile.update(count=1, dtype="uint8", nodata=255, compress="deflate", predictor=1)
        with rasterio.open(Path(output).parent / "external-ml-prediction.tif", "w", **profile) as dst:
            dst.write(tuned, 1)
    report = {
        "spatial_ml_training": training_report,
        "recall_policy": recall_policy,
        "source": SOURCE,
        "license": "CC BY 4.0 (Zenodo record)",
        "creator": "Ritu Yadav",
        "status": "EXTERNAL_FLOOD_BENCHMARK_ONLY",
        "sensor": "Sentinel-1 VV dB, first band; post minus pre",
        "label_scope": "Published hand labels for flood/water mapping; not generic radiometric change labels",
        "train_chips": list(TRAIN),
        "held_out_chip": HOLDOUT,
        "selection": "First matching chip in lexicographic order per selected country; distinct countries for fit and test",
        "weights": weights.tolist(),
        "feature_mean": mean.tolist(),
        "feature_scale": scale.tolist(),
        "train_samples": int(sum(map(len, targets))),
        "feature_order": ["after_vv_db", "delta_vv_db", "before_vv_db"],
        "evaluation": {
            name: metrics(truth, prediction) for name, prediction in predictions.items()
        },
        "inputs_sha256": sources,
        "limitations": [
            "One external holdout chip is a comparison, not a generalization claim.",
            "Flood/water labels cannot validate the Alaska NISAR scene.",
            "Logistic model was not applied to Alaska or transferred across sensors.",
        ],
    }
    write_json(Path(output), report)
    return report
