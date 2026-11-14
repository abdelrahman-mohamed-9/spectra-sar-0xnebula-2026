"""Verify this release's self-recorded SHA256 manifest (not a signature)."""
from pathlib import Path
import hashlib

root=Path(__file__).resolve().parents[1]
count=0
for line in (root/'FILE_MANIFEST.sha256').read_text().splitlines():
    expected,relative=line.split('  ',1)
    path=(root/relative).resolve()
    if not path.is_relative_to(root):raise SystemExit('Unsafe manifest path')
    if not path.is_file():raise SystemExit('Missing: '+relative)
    with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=expected:raise SystemExit('Mismatch: '+relative)
    count+=1
print(f'PASS: {count} files match this release manifest; not an authenticity signature.')
