#!/usr/bin/env python3
"""Create empty integration directories without overwriting members' code."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DIRS = [
    "contracts", "docs", "tests", "services/m1-sar-data", "services/m2-ai",
    "services/m3-impact", "services/m4-backend", "services/m5-frontend",
    "ops", "samples/README-only"
]
for relative in DIRS:
    folder = ROOT / relative
    folder.mkdir(parents=True, exist_ok=True)
    readme = folder / ".gitkeep"
    readme.touch(exist_ok=True)
print(f"PASS: {len(DIRS)} directory placeholders created; no member-owned sources overwritten")
