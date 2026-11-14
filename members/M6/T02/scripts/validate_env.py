#!/usr/bin/env python3
"""Validate local development secrets/config without printing secret values."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["POSTGRES_PASSWORD", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"]
PORTS = ["POSTGRES_PORT", "MINIO_PORT", "MINIO_CONSOLE_PORT"]

def load(path):
    if not path.is_file():
        raise ValueError(".env missing: copy .env.example to .env and set credentials")
    parsed = {}
    for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Malformed .env line {no}")
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", k):
            raise ValueError(f"Invalid key at line {no}")
        if k in parsed:
            raise ValueError(f"Duplicate key: {k}")
        parsed[k] = v
    return parsed

def validate(config):
    errors = []
    for k in REQUIRED:
        v = config.get(k, "")
        if not v or "CHANGE_ME" in v.upper():
            errors.append(f"{k} must be set to a non-placeholder value")
        elif k.endswith("PASSWORD") and len(v) < 16:
            errors.append(f"{k} must be at least 16 characters")
    for k in PORTS:
        v = config.get(k, "")
        if v:
            try:
                if not 1 <= int(v) <= 65535: raise ValueError()
            except ValueError:
                errors.append(f"{k} must be a valid port (1-65535)")
    specified = [config.get(k) for k in PORTS]
    if len(set(v for v in specified if v)) != len([v for v in specified if v]):
        errors.append("Published ports must be unique")
    return errors

if __name__ == "__main__":
    import sys
    try:
        errors = validate(load(ROOT / ".env"))
    except ValueError as err:
        errors = [str(err)]
    if errors:
        for msg in errors: print("ERROR:", msg)
        sys.exit(1)
    print("PASS: local environment config validated (service connectivity not tested)")
