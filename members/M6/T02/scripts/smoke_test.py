#!/usr/bin/env python3
"""Smoke test running local infrastructure using only the Python stdlib."""
import os
import socket
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_env import load, validate, ROOT

cfg = load(ROOT / ".env")
errors = validate(cfg)
if errors:
    for item in errors: print("FAIL:", item)
    sys.exit(1)

def tcp_check(host, port):
    with socket.create_connection((host, int(port)), timeout=3):
        return True

def http_check(url):
    with urllib.request.urlopen(url, timeout=4) as response:
        return 200 <= response.status < 300

checks = [
    ("PostgreSQL TCP listening (not authentication)", lambda: tcp_check("127.0.0.1", cfg.get("POSTGRES_PORT", "5432"))),
    ("MinIO readiness endpoint", lambda: http_check("http://127.0.0.1:" + cfg.get("MINIO_PORT", "9000") + "/minio/health/ready")),
]
failed = 0
for title, check in checks:
    try:
        check()
        print("PASS:", title)
    except Exception as e:
        failed += 1
        print("FAIL:", title, "-", type(e).__name__)
print("NOTE: This does not validate actual SAR processing, bucket creation, SQL authentication or API integration.")
sys.exit(1 if failed else 0)
