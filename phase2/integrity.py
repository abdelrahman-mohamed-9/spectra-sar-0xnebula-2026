"""Receipts across pipeline boundaries and verified snapshots for downloads."""

import hashlib
import os
import stat
from pathlib import Path

from .run_m2 import sha256


def safe(root, name):
    root = Path(root).resolve()
    parts = Path(name)
    if not parts.parts or parts.is_absolute() or ".." in parts.parts or "\\" in str(name):
        raise ValueError("Unsafe artifact path")
    candidate = root / parts
    if any(
        parent.is_symlink()
        for parent in (candidate, *candidate.parents)
        if parent.is_relative_to(root)
    ):
        raise ValueError("Artifact symlinks are forbidden")
    if not candidate.resolve().is_relative_to(root):
        raise ValueError("Artifact escapes storage")
    return candidate


def inventory(root, files):
    result = {}
    for item in sorted(files):
        path = safe(root, item)
        if not path.is_file():
            raise ValueError(f"Missing artifact: {item}")
        result[item] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    return result


def verify_inventory(root, receipt):
    if inventory(root, receipt) != receipt:
        raise ValueError("SHA-256 or size mismatch at pipeline boundary")


def verified_bytes(root, name, receipt):
    if receipt["bytes"] > 64 * 1024 * 1024:
        raise ValueError("Artifact exceeds download budget")
    file = safe(root, name)
    fd = os.open(file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Artifact is not a regular file")
        contents = stream.read(receipt["bytes"] + 1)
    if (
        len(contents) != receipt["bytes"]
        or hashlib.sha256(contents).hexdigest() != receipt["sha256"]
    ):
        raise ValueError("Artifact integrity failure")
    return contents
