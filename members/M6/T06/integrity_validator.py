"""Streaming local artifact integrity verification; no remote downloads or SAR simulation."""
from __future__ import annotations
import hashlib
import hmac
import re
from pathlib import Path

HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
CHUNK_SIZE = 1024 * 1024

class IntegrityError(ValueError):
    pass

def hash_file(path: str | Path) -> tuple[str, int]:
    path = Path(path)
    if not path.is_file():
        raise IntegrityError(f"not a regular file: {path}")
    digest = hashlib.sha256()
    byte_count = 0
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b''):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count

def verify_file(path: str | Path, sha256: str, bytes_size: int) -> bool:
    if not isinstance(sha256, str) or not HEX_SHA256.fullmatch(sha256):
        raise IntegrityError('sha256 must be 64 lowercase hex characters')
    if type(bytes_size) is not int or bytes_size < 0:
        raise IntegrityError('bytes_size must be a nonnegative integer')
    computed_sha, computed_size = hash_file(path)
    if computed_size != bytes_size:
        raise IntegrityError(f'byte size mismatch: expected {bytes_size}, got {computed_size}')
    if not hmac.compare_digest(computed_sha, sha256):
        raise IntegrityError('SHA-256 mismatch: file differs from recorded artifact')
    return True


def local_path_from_uri(uri: str, *, root: str | Path) -> Path:
    """Resolve relative file:// paths only within the trusted artifact root.

    This intentionally rejects absolute paths and object store URIs. S3/MinIO
    should be verified by a separately authenticated storage adapter.
    """
    if not isinstance(uri, str) or not uri.startswith('file://'):
        raise IntegrityError('only file:// artifacts supported by local verifier')
    relative = uri[len('file://'):]
    if not relative or relative.startswith('/') or '\\' in relative or '?' in relative or '#' in relative:
        raise IntegrityError('file URI must contain a simple relative path')
    root_path = Path(root).resolve(strict=True)
    candidate = (root_path / relative).resolve()
    if not candidate.is_relative_to(root_path):
        raise IntegrityError('file path escapes trusted root')
    return candidate
