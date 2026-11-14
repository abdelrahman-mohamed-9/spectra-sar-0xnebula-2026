"""SQLite-backed job queue with a separately launched analysis worker."""

import argparse
import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .integrity import verify_inventory

LOGGER = logging.getLogger(__name__)
CATALOG = Path(__file__).resolve().parents[1]


class JobLimitError(ValueError):
    pass


def utc_now():
    return datetime.now(UTC).isoformat()


class Jobs:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt" and self.root.stat().st_mode & 0o077:
            raise ValueError("Job data directory must be private (0700)")
        self.runs = self.root / "runs"
        self.runs.mkdir(mode=0o700, exist_ok=True)
        if self.runs.is_symlink():
            raise ValueError("Run storage cannot be a symlink")
        self.database = self.root / "jobs.sqlite3"
        if self.database.is_symlink():
            raise ValueError("Job database cannot be a symlink")
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    dataset TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN
                       ('QUEUED','RUNNING','COMPLETED_EXPLORATORY','FAILED')),
                    submitted_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error_code TEXT,
                    result TEXT,
                    receipt TEXT
                );
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status, submitted_at);
                CREATE INDEX IF NOT EXISTS jobs_owner ON jobs(owner, submitted_at);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, job_id TEXT NOT NULL,
                    state TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                );
                CREATE TABLE IF NOT EXISTS alert_reviews (
                    job_id TEXT NOT NULL, alert_id TEXT NOT NULL, reviewed_at TEXT NOT NULL,
                    PRIMARY KEY(job_id, alert_id), FOREIGN KEY(job_id) REFERENCES jobs(id)
                );
            """)
            columns = {r[1] for r in db.execute("PRAGMA table_info(jobs)")}
            if "candidate_mode" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN candidate_mode TEXT NOT NULL DEFAULT 'conservative'")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def event(db, job, state):
        db.execute(
            "INSERT INTO events(job_id,state,occurred_at) VALUES(?,?,?)",
            (job, state, utc_now()),
        )

    def submit(self, owner, dataset, candidate_mode="conservative"):
        if candidate_mode not in {"conservative", "review"}:
            raise ValueError("Unknown candidate mode")
        job = str(uuid4())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            pending = db.execute(
                "SELECT COUNT(*) FROM jobs WHERE owner=? AND status IN ('QUEUED','RUNNING')",
                (owner,),
            ).fetchone()[0]
            if pending >= 4:
                raise JobLimitError("Too many active jobs")
            db.execute(
                "INSERT INTO jobs(id,owner,dataset,status,submitted_at) VALUES(?,?,?,'QUEUED',?)",
                (job, owner, dataset, utc_now()),
            )
            db.execute("UPDATE jobs SET candidate_mode=? WHERE id=?", (candidate_mode, job))
            self.event(db, job, "QUEUED")
        return job

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id,dataset,candidate_mode FROM jobs WHERE status='QUEUED' ORDER BY submitted_at,id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE jobs SET status='RUNNING',started_at=? WHERE id=?",
                (utc_now(), row["id"]),
            )
            self.event(db, row["id"], "RUNNING")
            return dict(row)

    def get(self, owner, job):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE owner=? AND id=?", (owner, job)).fetchone()
            return dict(row) if row else None

    def finish(self, job, state, *, report=None, receipt=None, error=None):
        with self.connect() as db:
            updated = db.execute(
                """UPDATE jobs SET status=?,finished_at=?,result=?,receipt=?,error_code=?
                   WHERE id=? AND status='RUNNING'""",
                (state, utc_now(), json.dumps(report), json.dumps(receipt), error, job),
            )
            if updated.rowcount != 1:
                raise ValueError("Unexpected job state")
            self.event(db, job, state)

    def list(self, owner, limit=50):
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT id,dataset,status,submitted_at,finished_at,error_code,candidate_mode FROM jobs WHERE owner=? ORDER BY submitted_at DESC LIMIT ?",
                (owner, min(100, max(1, limit))))]

    def events(self, owner, job):
        if not self.get(owner, job):
            return None
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT state,occurred_at FROM events WHERE job_id=? ORDER BY id", (job,))]

    def recover_interrupted(self):
        """Only call after obtaining the exclusive worker lock."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ids = db.execute("SELECT id FROM jobs WHERE status='RUNNING'").fetchall()
            for row in ids:
                db.execute(
                    """UPDATE jobs SET status='FAILED',finished_at=?,error_code='WORKER_INTERRUPTED'
                       WHERE id=?""",
                    (utc_now(), row["id"]),
                )
                self.event(db, row["id"], "FAILED")

    @contextmanager
    def worker_lock(self):
        path = self.root / "worker.lock"
        if path.is_symlink():
            raise ValueError("Worker lock cannot be a symlink")
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "r+b") as lock:
            if os.name == "nt":
                import msvcrt
                if os.fstat(lock.fileno()).st_size == 0:
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    yield
                finally:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                yield


def work_one(queue, catalog=None):
    from .pipeline import execute

    row = queue.claim()
    if row is None:
        return None
    job = row["id"]
    directory = queue.runs / job
    try:
        if catalog is None:
            from .datasets import resolve
            catalog = resolve(queue.root, row["dataset"])
        report, receipt = execute(row["dataset"], catalog, directory, candidate_mode=row["candidate_mode"])
        verify_inventory(directory, receipt)
    except Exception:  # Worker must record any analysis failure, not leave a RUNNING job stranded.
        LOGGER.exception("Phase 2 job %s failed", job)
        queue.finish(job, "FAILED", error="ANALYSIS_OR_INTEGRITY_FAILED")
    else:
        queue.finish(job, "COMPLETED_EXPLORATORY", report=report, receipt=receipt)
    return job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=os.environ.get("SPECTRA_PHASE2_STATE"), required=False)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.state:
        parser.error("Set --state or SPECTRA_PHASE2_STATE")
    queue = Jobs(args.state)
    with queue.worker_lock():
        queue.recover_interrupted()
        if args.once:
            work_one(queue)
        else:
            while True:
                if work_one(queue) is None:
                    time.sleep(1)


if __name__ == "__main__":
    main()
