"""SPECTRA-SAR M2 T02: manifest-driven, windowed loading of M1 RTC rasters."""
from __future__ import annotations

import json
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
import rasterio
from rasterio.windows import Window


class PairInputError(ValueError):
    """Input is missing, malformed or outside the declared pair directory."""


def safe_pair_file(root: Path, filename: str) -> Path:
    if not isinstance(filename, str) or not filename or Path(filename).is_absolute():
        raise PairInputError(f"Invalid relative file name: {filename!r}")
    target = (root / filename).resolve()
    if not target.is_relative_to(root.resolve()) or target.suffix.lower() not in {'.tif', '.tiff'}:
        raise PairInputError(f"File path must be a GeoTIFF inside pair directory: {filename!r}")
    return target


def load_manifest(pair_dir: str | Path) -> dict:
    root = Path(pair_dir).resolve()
    manifest = root / 'manifest.json'
    if not manifest.is_file():
        raise PairInputError(f"Missing manifest: {manifest}")
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise PairInputError(f"Cannot read JSON manifest: {exc}") from exc
    if not isinstance(data, dict):
        raise PairInputError('Manifest root must be a JSON object')
    return data


@dataclass(frozen=True)
class RasterTile:
    window: Window
    before: np.ndarray
    after: np.ndarray
    valid: np.ndarray
    polarization: str


def iter_pair_tiles(pair_dir: str | Path, polarization: str = 'VV', tile_size: int = 512) -> Iterator[RasterTile]:
    """Yield float32 linear-power tiles and a conservative joint validity mask.

    Validation MUST be run first; this loader doesn't do geometric correction.
    Zero power is excluded from usable change-ratio pixels. Layover/shadow=1 is excluded.
    """
    if tile_size < 1:
        raise ValueError('tile_size must be positive')
    root = Path(pair_dir).resolve()
    doc = load_manifest(root)
    if polarization not in ('VV', 'VH', 'HHHH'):
        raise PairInputError('Only VV/VH (Sentinel-1) or HHHH (NISAR GCOV) supported')
    try:
        bmeta, ameta = doc['before'], doc['after']
        bfile = safe_pair_file(root, bmeta['raster_files'][polarization])
        afile = safe_pair_file(root, ameta['raster_files'][polarization])
        bmask = safe_pair_file(root, bmeta['valid_mask_file'])
        amask = safe_pair_file(root, ameta['valid_mask_file'])
        bshadow = safe_pair_file(root, bmeta['layover_shadow_mask_file']) if bmeta.get('layover_shadow_mask_file') else None
        ashadow = safe_pair_file(root, ameta['layover_shadow_mask_file']) if ameta.get('layover_shadow_mask_file') else None
    except (KeyError, TypeError) as exc:
        raise PairInputError(f'Missing manifest field: {exc}') from exc

    with ExitStack() as stack:
        handles = [stack.enter_context(rasterio.open(p)) for p in [bfile, afile, bmask, amask]]
        hbs = stack.enter_context(rasterio.open(bshadow)) if bshadow else None
        has = stack.enter_context(rasterio.open(ashadow)) if ashadow else None
        b, a, bm, am = handles
        signature = (b.crs, b.transform, b.width, b.height)
        if any((d.crs, d.transform, d.width, d.height) != signature for d in [a, bm, am] + [d for d in (hbs, has) if d]):
            raise PairInputError('Raster grids mismatch; run validator and request M1 regrid')
        for row in range(0, b.height, tile_size):
            for col in range(0, b.width, tile_size):
                win = Window(col, row, min(tile_size, b.width-col), min(tile_size, b.height-row))
                bv, av = b.read(1, window=win), a.read(1, window=win)
                valid = ((bm.read(1, window=win) == 1) & (am.read(1, window=win) == 1)
                         & (b.read_masks(1, window=win) > 0) & (a.read_masks(1, window=win) > 0)
                         & np.isfinite(bv) & np.isfinite(av) & (bv > 0) & (av > 0))
                if hbs:
                    valid &= hbs.read(1, window=win) == 0
                if has:
                    valid &= has.read(1, window=win) == 0
                yield RasterTile(win, bv, av, valid, polarization)
