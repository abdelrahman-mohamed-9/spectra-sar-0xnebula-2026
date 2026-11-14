"""Bounded streaming validation; extension and content signatures must agree."""
from __future__ import annotations
from pathlib import Path
from fastapi import HTTPException

ALLOWED = {
    '.tif': ('image/tiff', 'tiff'), '.tiff': ('image/tiff', 'tiff'),
    '.png': ('image/png', 'png'), '.json': ('application/json', 'json'),
    '.geojson': ('application/geo+json', 'json'),
    '.zip': ('application/zip', 'zip'),
}

def validate_name(name: str | None) -> tuple[str, str]:
    if not name or '/' in name or '\\' in name or name.startswith('.') or len(name)>180:
        raise HTTPException(422, 'Invalid file name')
    ext=Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(415, 'File extension not supported')
    return ext, ALLOWED[ext][0]

def validate_signature(ext: str, first: bytes) -> None:
    if ext in {'.tif','.tiff'}:
        ok=first[:4] in (b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+')
    elif ext == '.png':
        ok=first.startswith(b'\x89PNG\r\n\x1a\n')
    elif ext == '.zip':
        ok=first.startswith(b'PK\x03\x04')
    else:
        ok=first.lstrip(b'\xef\xbb\xbf \r\n\t').startswith((b'{',b'['))
    if not ok:
        raise HTTPException(415,'File signature does not match extension')
