import hashlib
import shutil

import numpy as np
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from scipy.ndimage import gaussian_filter, shift

from phase2.api import build_router, local_identity
from phase2.jobs import CATALOG, Jobs, work_one
from phase2.m1 import alignment, regrid

BASE = "/api/v1/phase2/jobs"


def app_for(queue):
    app = FastAPI()

    def identity(x_test_actor: str | None = Header(default=None)):
        if x_test_actor not in {"A", "B"}:
            raise HTTPException(401, "Invalid fixture identity")
        return x_test_actor

    app.include_router(build_router(queue, identity))
    return app


def test_backend_worker_full_real_run_and_tamper(tmp_path):
    queue = Jobs(tmp_path / "private")
    headers = {"X-Test-Actor": "A"}
    with TestClient(app_for(queue)) as client:
        assert client.post(BASE, json={}).status_code == 401
        assert client.post(BASE, json={"dataset": "../path"}, headers=headers).status_code == 404
        submitted = client.post(BASE, json={}, headers=headers)
        assert submitted.status_code == 202
        job = submitted.json()["id"]
        route = f"{BASE}/{job}"
        assert client.get(route, headers=headers).json()["status"] == "QUEUED"
        assert client.get(route + "/artifacts", headers=headers).status_code == 409
    assert work_one(queue) == job
    restarted = Jobs(queue.root)
    with TestClient(app_for(restarted)) as client:
        assert client.get(route, headers={"X-Test-Actor": "B"}).status_code == 404
        assert client.get(route + "/artifacts", headers={"X-Test-Actor": "B"}).status_code == 404
        result = client.get(route, headers=headers).json()
        assert result["status"] == "COMPLETED_EXPLORATORY"
        assert result["result"]["scientific_approval"] is False
        assert result["result"]["m2"]["candidate_pixels"] == 566
        receipt = client.get(route + "/artifacts", headers=headers).json()
        path = route + "/artifacts/M2/adaptive_change_mask.tif"
        mask = client.get(path, headers=headers)
        digest = hashlib.sha256(mask.content).hexdigest()
        assert mask.status_code == 200 and digest == mask.headers["X-Artifact-Sha256"]
        assert digest == receipt["M2/adaptive_change_mask.tif"]["sha256"]
        impact = client.get(route + "/artifacts/M3/impact-report.json", headers=headers).json()
        assert impact["census_coverage_fraction"] > 0.99
        assert impact["census_block_context"][0]["census_2020_population"] == 2
        assert impact["estimated_residents_exposed"] is None
        evaluation = client.get(
            route + "/artifacts/external-evaluation.json", headers=headers
        ).json()
        assert evaluation["held_out_chip"] not in evaluation["train_chips"]
        assert evaluation["evaluation"]["robust_darkening"]["recall"] < 0.1
        (queue.runs / job / "M2/adaptive_change_mask.tif").write_bytes(b"changed")
        assert client.get(path, headers=headers).status_code == 409
        assert (
            client.get(route + "/artifacts/%2e%2e/jobs.sqlite3", headers=headers).status_code == 404
        )
    with restarted.connect() as db:
        assert [r[0] for r in db.execute("SELECT state FROM events ORDER BY id")] == [
            "QUEUED",
            "RUNNING",
            "COMPLETED_EXPLORATORY",
        ]


def test_corrupted_catalog_input_blocks_worker(tmp_path):
    catalog = tmp_path / "catalog"
    shutil.copytree(CATALOG / "data", catalog / "data")
    shutil.copyfile(CATALOG / "catalog.json", catalog / "catalog.json")
    (catalog / "data/nisar/before_HHHH.tif").write_bytes(b"changed")
    queue = Jobs(tmp_path / "private")
    job = queue.submit("A", "nisar-oct2026")
    assert work_one(queue, catalog) == job
    record = queue.get("A", job)
    assert record["status"] == "FAILED"
    assert record["error_code"] == "ANALYSIS_OR_INTEGRITY_FAILED"
    assert not (queue.runs / job / "M1").exists()


def test_abandoned_job_recovery_preserves_queue(tmp_path):
    queue = Jobs(tmp_path / "private")
    first = queue.submit("A", "nisar-oct2026")
    assert queue.claim()["id"] == first
    second = queue.submit("A", "nisar-oct2026")
    with queue.worker_lock():
        queue.recover_interrupted()
    assert queue.get("A", first)["error_code"] == "WORKER_INTERRUPTED"
    assert queue.claim()["id"] == second


def test_fractional_registration_on_controlled_fixture():
    rng = np.random.default_rng(4)
    before = np.exp(gaussian_filter(rng.normal(size=(256, 256)), 1.2))
    after = shift(before, (0.65, -0.55), order=3, mode="nearest")
    valid = np.ones(before.shape, dtype=bool)
    _, after_valid, report = alignment(before, after, valid, valid)
    assert report["status"] == "INTERNAL_HOLDOUT_IMPROVED"
    assert np.allclose(report["applied_shift_rc"], [-0.65, 0.55], atol=0.15)
    assert report["holdout_p90_residual_after_px"] < report["holdout_p90_residual_before_px"]
    assert not after_valid.all()
    assert report["independently_certified"] is False


def test_regrid_removes_invalid_interpolation_support():
    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    crs = CRS.from_epsg(32605)
    data = np.full((8, 8), 2, dtype="float32")
    valid = np.ones(data.shape, dtype=bool)
    valid[3, 3] = False
    source = crs, from_origin(400000, 7000000, 10, 10), data.shape
    target = crs, from_origin(400005, 7000000, 10, 10), data.shape
    result, support = regrid(data, valid, source, target)
    assert np.allclose(result[support], 2)
    assert not support[3, 2] and not support[3, 3]
    assert np.isnan(result[~support]).all()


def test_local_bearer_credentials(tmp_path):
    token = "test-fixture-" * 4
    app = FastAPI()
    app.include_router(build_router(Jobs(tmp_path / "private"), local_identity(token)))
    with TestClient(app) as client:
        assert client.post(BASE, json={}).status_code == 401
        assert (
            client.post(BASE, json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
        )
        assert (
            client.post(BASE, json={}, headers={"Authorization": f"Bearer {token}"}).status_code
            == 202
        )
