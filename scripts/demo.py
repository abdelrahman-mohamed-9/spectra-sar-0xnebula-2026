"""Run one real dataset through HTTP, a separate worker, and SQLite."""

import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def local_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_api(client, server):
    # Heavy geospatial imports can exceed ten seconds on busy machines.
    for _ in range(450):
        if server.poll() is not None:
            raise RuntimeError("API exited before startup")
        try:
            if client.get("/openapi.json").status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise TimeoutError("API startup timed out")


def demo(state):
    token = secrets.token_urlsafe(32)
    env = {**os.environ, "SPECTRA_PHASE2_STATE": str(state), "SPECTRA_PHASE2_TOKEN": token}
    port = local_port()
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "phase2.application:create_local_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    with subprocess.Popen(command, env=env) as server:
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False) as client:
                wait_api(client, server)
                base = "/api/v1/phase2/jobs"
                assert client.post(base, json={}).status_code == 401
                client.headers["Authorization"] = f"Bearer {token}"
                submission = client.post(base, json={})
                submission.raise_for_status()
                job = submission.json()["id"]
                endpoint = f"{base}/{job}"
                assert client.get(endpoint).json()["status"] == "QUEUED"
                subprocess.run(
                    [sys.executable, "-m", "phase2.jobs", "--once"],
                    env=env,
                    check=True,
                    timeout=120,
                )
                status = client.get(endpoint)
                status.raise_for_status()
                job_record = status.json()
                if job_record["status"] != "COMPLETED_EXPLORATORY":
                    raise RuntimeError(f"Job {job} failed: {job_record['error_code']}")
                listing = client.get(f"{endpoint}/artifacts")
                listing.raise_for_status()
                receipts = listing.json()
                for name, receipt in receipts.items():
                    response = client.get(f"{endpoint}/artifacts/{name}")
                    response.raise_for_status()
                    digest = hashlib.sha256(response.content).hexdigest()
                    if (
                        digest != receipt["sha256"]
                        or digest != response.headers["X-Artifact-Sha256"]
                    ):
                        raise ValueError(f"Download integrity failed: {name}")
                return {**job_record, "artifacts_retrieved_and_verified": len(receipts)}
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(demo(args.state.resolve()), indent=2))


if __name__ == "__main__":
    main()
