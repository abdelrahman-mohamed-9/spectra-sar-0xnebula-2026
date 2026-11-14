"""M5 FastAPI routes for starting jobs and retrieving verified results."""

import hashlib
import hmac
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Response, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from .integrity import verified_bytes
from .jobs import CATALOG, JobLimitError, Jobs

DATASET = "nisar-oct2026"
bearer = HTTPBearer(auto_error=False)


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = DATASET
    candidate_mode: Literal["conservative", "review"] = "conservative"


def build_router(queue: Jobs, identity: Callable):
    router = APIRouter(prefix="/api/v1/phase2", tags=["phase2"])

    def owned(job, owner):
        row = queue.get(str(owner), str(job))
        if row is None:
            raise HTTPException(404, "Job not found")
        return row

    Owner = Annotated[str, Depends(identity)]

    @router.post("/jobs", status_code=202)
    def submit(request: Submission, owner: Owner):
        from .datasets import resolve
        try:
            resolve(queue.root, request.dataset)
        except ValueError as exc:
            raise HTTPException(404, "Dataset not found") from exc
        try:
            job = queue.submit(str(owner), request.dataset, request.candidate_mode)
        except JobLimitError as exc:
            raise HTTPException(429, "Too many active jobs") from exc
        return {"id": job, "status": "QUEUED"}

    @router.get("/datasets")
    def datasets(owner: Owner):
        from .datasets import listing
        return listing(queue.root)

    @router.get("/jobs")
    def recent(owner: Owner):
        return queue.list(str(owner))

    @router.get("/jobs/{job_id}/events")
    def events(job_id: UUID, owner: Owner):
        owned(job_id, owner)
        return queue.events(str(owner), str(job_id))

    @router.get("/jobs/{job_id}")
    def status(job_id: UUID, owner: Owner):
        row = owned(job_id, owner)
        return {
            "id": row["id"],
            "dataset": row["dataset"],
            "candidate_mode": row["candidate_mode"],
            "status": row["status"],
            "submitted_at": row["submitted_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "error_code": row["error_code"],
            "result": json.loads(row["result"]) if row["result"] else None,
        }

    def artifacts(job_id, owner):
        row = owned(job_id, owner)
        if row["status"] != "COMPLETED_EXPLORATORY":
            raise HTTPException(409, "Job results are unavailable")
        return json.loads(row["receipt"])

    @router.get("/jobs/{job_id}/artifacts")
    def listing(job_id: UUID, owner: Owner):
        return artifacts(job_id, owner)

    @router.get("/jobs/{job_id}/phase3")
    def advanced(job_id: UUID, owner: Owner):
        receipts = artifacts(job_id, owner)
        result = {}
        for key, name in (("analysis", "analysis.json"), ("zones", "risk-zones.geojson"), ("evidence", "processing-log.json")):
            name = "Phase3/" + name
            if name not in receipts:
                raise HTTPException(404, "Phase 3 is not available for this historical run")
            try:
                result[key] = json.loads(verified_bytes(queue.runs / str(job_id), name, receipts[name]))
            except (OSError, ValueError) as exc:
                raise HTTPException(409, "Phase 3 integrity check failed") from exc
        return result

    @router.get("/jobs/{job_id}/artifacts/{name:path}")
    def download(job_id: UUID, name: str, owner: Owner):
        receipt = artifacts(job_id, owner).get(name)
        if receipt is None:
            raise HTTPException(404, "Artifact not found")
        try:
            contents = verified_bytes(queue.runs / str(job_id), name, receipt)
        except (OSError, ValueError) as exc:
            raise HTTPException(409, "Artifact integrity check failed") from exc
        content_type = "image/png" if name.endswith(".png") else "application/json" if name.endswith((".json", ".geojson")) else "application/octet-stream"
        return Response(
            contents,
            media_type=content_type,
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'attachment; filename="{Path(name).name}"',
                "X-Artifact-Sha256": receipt["sha256"],
            },
        )

    def completed(job_id, owner):
        row = owned(job_id, owner)
        if row['status'] != 'COMPLETED_EXPLORATORY':
            raise HTTPException(409, 'Analysis must complete first')
        return row

    def checked(operation):
        try:
            return operation()
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(409, 'Required evidence is missing, incompatible or failed integrity verification') from exc

    @router.get('/jobs/{job_id}/insights')
    def explanations(job_id: UUID, owner: Owner):
        from .experience import insights
        row = completed(job_id, owner)
        result = checked(lambda: insights(queue, row))
        with queue.connect() as db:
            reviewed = {entry['alert_id']:entry['reviewed_at'] for entry in db.execute('SELECT alert_id,reviewed_at FROM alert_reviews WHERE job_id=?',(str(job_id),))}
        for alert in result['alerts']:
            alert['reviewed_at'] = reviewed.get(alert['id'])
        return result

    @router.put('/jobs/{job_id}/alerts/{alert_id}/review')
    def review_alert(job_id: UUID, alert_id: str, owner: Owner):
        from .experience import insights
        from .jobs import utc_now
        row = completed(job_id, owner)
        result = checked(lambda: insights(queue, row))
        if alert_id not in {alert['id'] for alert in result['alerts']}:
            raise HTTPException(404, 'Alert not found')
        with queue.connect() as db:
            db.execute('INSERT OR IGNORE INTO alert_reviews(job_id,alert_id,reviewed_at) VALUES(?,?,?)',(str(job_id),alert_id,utc_now()))
        return {'status':'reviewed','alert_id':alert_id}

    @router.get('/jobs/{job_id}/compare/{other_id}')
    def compare_runs(job_id: UUID, other_id: UUID, owner: Owner):
        from .experience import comparison
        left, right = completed(job_id, owner), completed(other_id, owner)
        return checked(lambda: comparison(queue,left,right))

    @router.get('/jobs/{job_id}/report')
    def portable_report(job_id: UUID, owner: Owner):
        from .experience import report_html
        row = completed(job_id, owner)
        contents = checked(lambda: report_html(queue,row))
        return Response(contents, media_type='text/html', headers={'Content-Disposition':f'attachment; filename="SPECTRA-{job_id}.html"','Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; img-src data:; style-src 'unsafe-inline'; sandbox"})

    @router.post('/jobs/{job_id}/glacier')
    async def glacier_upload(job_id: UUID, request: Request, owner: Owner):
        from .glacier import analyze_bundle, MAX_BYTES
        from .experience import document
        from uuid import uuid4
        import zipfile
        from rasterio.errors import RasterioError
        from starlette.concurrency import run_in_threadpool
        row = completed(job_id, owner)
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > MAX_BYTES:
                raise HTTPException(413, 'Bundle exceeds 32 MB')
        aoi = checked(lambda: document(queue,row,'Phase3/analysis.json')['bounds_wgs84'])
        try:
            result = await run_in_threadpool(analyze_bundle, bytes(payload), aoi)
        except (ValueError, KeyError, OSError, zipfile.BadZipFile, TypeError, RasterioError, RuntimeError) as exc:
            raise HTTPException(422, 'Invalid glacier bundle: '+str(exc)) from exc
        identifier = str(uuid4())
        target = queue.runs / str(job_id) / 'glacier-supplements' / identifier
        target.mkdir(parents=True)
        (target/'source.zip').write_bytes(payload)
        result['id'] = identifier
        result['job_id'] = str(job_id)
        raw = json.dumps(result,indent=2).encode()
        (target/'result.json').write_bytes(raw)
        with queue.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS glacier_results (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, result_sha256 TEXT NOT NULL, source_sha256 TEXT NOT NULL)')
            db.execute('INSERT INTO glacier_results VALUES (?,?,?,?)',(identifier,str(job_id),hashlib.sha256(raw).hexdigest(),result['source_sha256']))
        return result

    @router.get('/jobs/{job_id}/glacier')
    def glacier_results(job_id: UUID, owner: Owner):
        completed(job_id, owner)
        with queue.connect() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='glacier_results'").fetchone()
            if not exists:
                return []
            rows = db.execute('SELECT * FROM glacier_results WHERE job_id=? ORDER BY rowid DESC',(str(job_id),)).fetchall()
        results = []
        for entry in rows:
            folder = queue.runs / str(job_id) / 'glacier-supplements' / entry['id']
            def read_result():
                raw = (folder/'result.json').read_bytes()
                source = (folder/'source.zip').read_bytes()
                if hashlib.sha256(raw).hexdigest() != entry['result_sha256'] or hashlib.sha256(source).hexdigest() != entry['source_sha256']:
                    raise ValueError('Glacier evidence hash mismatch')
                return json.loads(raw)
            results.append(checked(read_result))
        return results

    return router


def local_identity(configured):
    if not configured or len(configured) < 32 or not configured.isascii():
        raise ValueError("Configure an ASCII SPECTRA_PHASE2_TOKEN of at least 32 characters")
    expected = hashlib.sha256(configured.encode()).digest()

    def identity(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ):
        if credentials is not None and len(credentials.credentials) <= 4096:
            supplied = hashlib.sha256(credentials.credentials.encode()).digest()
            if hmac.compare_digest(supplied, expected):
                return "local-operator"
        raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"})

    return identity


def create_app():
    state = os.environ.get("SPECTRA_PHASE2_STATE")
    if not state:
        raise ValueError("Configure SPECTRA_PHASE2_STATE")
    if not (CATALOG / "catalog.json").is_file():
        raise ValueError("Dataset catalog is missing")
    app = FastAPI(title="SPECTRA-SAR Phase 2", version="2.0")
    app.include_router(
        build_router(Jobs(state), local_identity(os.environ.get("SPECTRA_PHASE2_TOKEN")))
    )
    return app
