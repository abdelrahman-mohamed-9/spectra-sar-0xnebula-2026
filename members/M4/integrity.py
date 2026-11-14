"""SPECTRA-SAR M4/T02: byte-level SHA-256 integrity verification.

Standard library only. Integrity does NOT establish satellite-source authenticity,
scientific validity, or trust in a manifest that an attacker can also replace.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

CHUNK_SIZE = 1024 * 1024
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
VERSION = "1.0"


class IntegrityError(ValueError):
    """An input or integrity-baseline validation error."""


def _checked_file(path: Path) -> None:
    # Do not follow final-component symlinks, including file symlink chains.
    if path.is_symlink():
        raise IntegrityError(f"SYMLINK_REJECTED: {path}")
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise IntegrityError(f"FILE_UNAVAILABLE: {path}: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise IntegrityError(f"NOT_REGULAR_FILE: {path}")


def hash_file(path: str | Path) -> str:
    """SHA-256 of the actual raw bytes; streams large Sentinel-1 products."""
    p = Path(path)
    _checked_file(p)
    digest = hashlib.sha256()
    try:
        with p.open("rb") as stream:
            while block := stream.read(CHUNK_SIZE):
                digest.update(block)
    except OSError as exc:
        raise IntegrityError(f"READ_ERROR: {p}: {exc}") from exc
    return digest.hexdigest()


def verify_file(path: str | Path, expected_digest: str) -> dict[str, Any]:
    """Fail closed if digest missing/invalid or file unreadable."""
    p = Path(path)
    if not isinstance(expected_digest, str) or not HEX_SHA256.fullmatch(expected_digest):
        return {"status": "FAIL", "reason": "INVALID_EXPECTED_DIGEST", "observed_digest": None}
    try:
        observed = hash_file(p)
    except IntegrityError as exc:
        return {"status": "FAIL", "reason": str(exc), "observed_digest": None}
    match = hmac.compare_digest(observed, expected_digest)
    return {
        "status": "PASS" if match else "FAIL",
        "reason": "HASH_MATCH" if match else "HASH_MISMATCH",
        "observed_digest": observed,
    }


def _safe_relative_path(raw: Any, root: Path) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
        raise IntegrityError("INVALID_ARTIFACT_PATH")
    rel = PurePosixPath(raw)
    if rel.is_absolute() or any(part in {"..", "."} for part in raw.split("/")) or not rel.parts:
        raise IntegrityError(f"PATH_TRAVERSAL_REJECTED: {raw}")
    candidate = root / Path(*rel.parts)
    # Check every existing parent for symlink escapes, and require containment.
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise IntegrityError(f"PATH_ESCAPE_REJECTED: {raw}")
    for parent in (candidate, *candidate.parents):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise IntegrityError(f"SYMLINK_REJECTED: {raw}")
    return candidate


def _read_manifest(path: Path) -> dict[str, Any]:
    _checked_file(path)
    try:
        def no_duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in items:
                if key in result:
                    raise IntegrityError(f"DUPLICATE_JSON_KEY: {key}")
                result[key] = value
            return result
        doc = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"INVALID_MANIFEST: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema_version") != VERSION or doc.get("algorithm") != "sha256":
        raise IntegrityError("UNSUPPORTED_MANIFEST_FORMAT")
    entries = doc.get("artifacts")
    if not isinstance(entries, list) or not entries:
        raise IntegrityError("EMPTY_OR_INVALID_ARTIFACTS")
    names: set[str] = set()
    for record in entries:
        if not isinstance(record, dict):
            raise IntegrityError("INVALID_ARTIFACT_RECORD")
        name = record.get("path")
        if not isinstance(name, str) or name in names:
            raise IntegrityError("INVALID_OR_DUPLICATE_ARTIFACT_PATH")
        names.add(name)
        if not isinstance(record.get("size_bytes"), int) or isinstance(record.get("size_bytes"), bool) or record["size_bytes"] < 0:
            raise IntegrityError(f"INVALID_ARTIFACT_SIZE: {name}")
        if not isinstance(record.get("sha256"), str) or not HEX_SHA256.fullmatch(record["sha256"]):
            raise IntegrityError(f"INVALID_ARTIFACT_DIGEST: {name}")
    return doc


def create_manifest(root: Path, manifest: Path, rel_paths: list[str]) -> dict[str, Any]:
    if manifest.exists() or manifest.is_symlink():
        raise IntegrityError("MANIFEST_ALREADY_EXISTS: use a fresh path; never overwrite a trusted baseline")
    if not rel_paths:
        raise IntegrityError("NO_INPUT_FILES")
    if len(set(rel_paths)) != len(rel_paths):
        raise IntegrityError("DUPLICATE_INPUT_PATHS")
    artifacts = []
    for rel in sorted(rel_paths):
        p = _safe_relative_path(rel, root)
        _checked_file(p)
        if p.resolve() == manifest.resolve():
            raise IntegrityError("MANIFEST_CANNOT_HASH_ITSELF")
        before = p.stat()
        digest = hash_file(p)
        after = p.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise IntegrityError(f"FILE_CHANGED_DURING_HASH: {rel}")
        artifacts.append({"path": rel, "size_bytes": after.st_size, "sha256": digest})
    doc = {"schema_version": VERSION, "algorithm": "sha256", "created_at_utc": datetime.now(timezone.utc).isoformat(), "artifacts": artifacts}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create: no accidental replacement of trusted baseline.
    try:
        with manifest.open("x", encoding="utf-8") as stream:
            json.dump(doc, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except OSError as exc:
        raise IntegrityError(f"MANIFEST_WRITE_FAILED: {exc}") from exc
    return doc


def verify_manifest(root: Path, manifest: Path) -> dict[str, Any]:
    doc = _read_manifest(manifest)
    results: list[dict[str, Any]] = []
    for record in doc["artifacts"]:
        rel = record["path"]
        try:
            p = _safe_relative_path(rel, root)
            result = verify_file(p, record["sha256"])
            if result["status"] == "PASS" and p.stat().st_size != record["size_bytes"]:
                result = {"status": "FAIL", "reason": "SIZE_MISMATCH", "observed_digest": result["observed_digest"]}
        except (IntegrityError, OSError) as exc:
            result = {"status": "FAIL", "reason": str(exc), "observed_digest": None}
        results.append({"path": rel, **result})
    passes = sum(r["status"] == "PASS" for r in results)
    return {"status": "PASS" if passes == len(results) else "FAIL", "verified": passes, "total": len(results), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SPECTRA-SAR SHA-256 file integrity tool (M4/T02)")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("hash", help="Hash one real file")
    one.add_argument("file")
    check = sub.add_parser("check", help="Compare one file against an existing expected SHA-256")
    check.add_argument("file")
    check.add_argument("expected_sha256")
    create = sub.add_parser("create", help="Create a new baseline manifest (exclusive, never overwrite)")
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--manifest", type=Path, required=True)
    create.add_argument("files", nargs="+")
    verify = sub.add_parser("verify", help="Verify all files against an existing baseline")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "hash":
            result = {"file": args.file, "sha256": hash_file(args.file)}
        elif args.command == "check":
            result = {"file": args.file, **verify_file(args.file, args.expected_sha256)}
        elif args.command == "create":
            result = create_manifest(args.root, args.manifest, args.files)
        else:
            result = verify_manifest(args.root, args.manifest)
        print(json.dumps(result, indent=2))
        return 1 if result.get("status") == "FAIL" else 0
    except IntegrityError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
