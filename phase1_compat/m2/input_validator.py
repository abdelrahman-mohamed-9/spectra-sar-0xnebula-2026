"""SPECTRA-SAR M2 T02: scientific and geometric preflight of M1 imagery.

CLI: python input_validator.py /path/to/pair --output qa-report.json
Exit codes: 0 PASS, 2 WARNING, 3 REJECT.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

import numpy as np
import rasterio

from data_loader import PairInputError, load_manifest, safe_pair_file


def inspect_pair(pair_dir: str | Path, *, tile_size: int = 512) -> dict:
    root = Path(pair_dir).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    info: dict = {}

    def reject(message: str) -> None:
        errors.append(message)

    def warn(message: str) -> None:
        warnings.append(message)

    try:
        d = load_manifest(root)
    except PairInputError as exc:
        return {'status': 'REJECT', 'errors': [str(exc)], 'warnings': [], 'info': {}}

    sensor = d.get('sensor', 'Sentinel-1')
    if sensor == 'NISAR':
        expected_fields = [('schema_version','1.0'),('product_type','GCOV'),('acquisition_mode','4005'),
                           ('radiometry','nisar_gcov_diagonal'),('units','linear_power')]
    elif sensor == 'Sentinel-1':
        expected_fields = [('schema_version','1.0'),('product_type','RTC'),('acquisition_mode','IW'),
                           ('radiometry','gamma0_terrain'),('units','linear_power')]
    else:
        reject('Unsupported sensor; expected Sentinel-1 or NISAR')
        expected_fields=[]
    for key, expected in expected_fields:
        if d.get(key) != expected:
            reject(f'{key}: expected {expected!r}, got {d.get(key)!r}')
    for key in ('pair_id', 'source_provider', 'processing_software', 'processing_version'):
        if not isinstance(d.get(key), str) or not d[key].strip() or d[key].startswith('<'):
            reject(f'{key}: missing or placeholder')
    pols = d.get('polarizations')
    allowed_pols = ('HHHH',) if sensor == 'NISAR' else ('VV','VH')
    required_pol = 'HHHH' if sensor == 'NISAR' else 'VV'
    if not isinstance(pols,list) or required_pol not in pols or len(set(map(str,pols))) != len(pols) or any(x not in allowed_pols for x in pols):
        reject(f'polarizations: expected {required_pol}; valid set: {allowed_pols}')
        pols = [required_pol]
    grid = d.get('grid')
    if not isinstance(grid, dict):
        reject('grid: missing object')
        grid = {}
    scenes = {}
    for side in ('before', 'after'):
        scene = d.get(side)
        if not isinstance(scene, dict):
            reject(f'{side}: missing scene object')
            scene = {}
        scenes[side] = scene
        for key in ('scene_id', 'acquired_utc'):
            val = scene.get(key)
            if not isinstance(val, str) or not val.strip() or val.startswith('<'):
                reject(f'{side}.{key}: missing or placeholder')
        dt_str = scene.get('acquired_utc')
        if isinstance(dt_str, str):
            try:
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
                    raise ValueError('timestamp must be UTC')
                info[f'{side}_acquired_utc'] = dt.isoformat()
            except ValueError:
                reject(f'{side}.acquired_utc: must be a valid UTC ISO8601 timestamp')
        orbit = scene.get('relative_orbit')
        if type(orbit) is not int or not 1 <= orbit <= 175:
            reject(f'{side}.relative_orbit: integer 1..175 required')
        if scene.get('orbit_direction') not in ('ASCENDING', 'DESCENDING'):
            reject(f'{side}.orbit_direction: invalid')
        angle = scene.get('incidence_angle_deg_summary')
        if angle is not None and (isinstance(angle, bool) or not isinstance(angle, (int, float)) or not math.isfinite(angle) or not (0 < angle < 90)):
            reject(f'{side}.incidence_angle_deg_summary: expected degrees 0..90 or null')
        elif angle is None:
            warn(f'{side}: incidence-angle summary missing; scene pairing QA incomplete')
        if not isinstance(scene.get('raster_files'), dict):
            reject(f'{side}.raster_files: missing map')
        if not scene.get('valid_mask_file'):
            reject(f'{side}.valid_mask_file: missing')

    b, a = scenes['before'], scenes['after']
    for field in ('relative_orbit', 'orbit_direction'):
        if b.get(field) != a.get(field):
            reject(f'Pair {field} mismatch')
    if b.get('scene_id') and b.get('scene_id') == a.get('scene_id'):
        reject('Both timestamps refer to same scene ID')
    if 'before_acquired_utc' in info and 'after_acquired_utc' in info:
        if info['before_acquired_utc'] >= info['after_acquired_utc']:
            reject('Before timestamp must predate after timestamp')
    bi, ai = b.get('incidence_angle_deg_summary'), a.get('incidence_angle_deg_summary')
    if isinstance(bi, (int, float)) and isinstance(ai, (int, float)) and not isinstance(bi, bool) and not isinstance(ai, bool) and all(math.isfinite(v) for v in (bi, ai)):
        info['incidence_angle_difference_deg'] = round(abs(bi-ai), 4)
        if abs(bi-ai) > 2:
            warn('Incidence angle difference > 2°; manual scientific review required (heuristic)')

    rasters: dict[str, tuple[Path, str]] = {}
    for side, scene in scenes.items():
        declared = scene.get('raster_files') if isinstance(scene.get('raster_files'), dict) else {}
        for pol in pols:
            if pol not in declared:
                reject(f'{side}.{pol}: missing image')
            else:
                try:
                    rasters[f'{side}_{pol}'] = (safe_pair_file(root, declared[pol]), 'power')
                except PairInputError as exc:
                    reject(str(exc))
        for k, label in [('valid_mask_file', 'valid'), ('layover_shadow_mask_file', 'shadow')]:
            if k in scene and scene[k]:
                try:
                    rasters[f'{side}_{label}'] = (safe_pair_file(root, scene[k]), label)
                except PairInputError as exc:
                    reject(str(exc))
    if errors:
        return {'status': 'REJECT', 'errors': errors, 'warnings': warnings, 'info': info}

    from contextlib import ExitStack
    with ExitStack() as stack:
        opened = {}
        for label, (path, kind) in rasters.items():
            if not path.is_file():
                reject(f'{label}: missing file {path.name}')
                continue
            try:
                opened[label] = stack.enter_context(rasterio.open(path))
            except (rasterio.errors.RasterioError, OSError) as exc:
                reject(f'{label}: unreadable GeoTIFF: {exc}')
        if errors:
            return {'status': 'REJECT', 'errors': errors, 'warnings': warnings, 'info': info}
        baseline = opened[f'before_{required_pol}']
        if baseline.crs is None or not baseline.crs.is_projected:
            reject('CRS must be a projected metric coordinate system (UTM baseline)')
        else:
            crs_unit = str(baseline.crs.linear_units).lower()
            if crs_unit not in ('metre', 'meter', 'metres', 'meters'):
                reject(f'Projected CRS unit must be metres, got {crs_unit}')
        if baseline.width == 0 or baseline.height == 0:
            reject('Zero-sized raster')
        transform = baseline.transform
        if transform.b != 0 or transform.d != 0 or transform.a <= 0 or transform.e >= 0:
            reject('Expected north-up non-rotated raster grid')
        if abs(transform.a) < 1e-9 or abs(transform.e) < 1e-9:
            reject('Invalid pixel size')
        info['raster_shape'] = [baseline.height, baseline.width]
        info['crs'] = str(baseline.crs)
        info['pixel_size_xy'] = [abs(transform.a), abs(transform.e)]
        for label, ds in opened.items():
            if ds.driver != 'GTiff' or ds.count != 1:
                reject(f'{label}: single-band GeoTIFF required')
            if (ds.crs != baseline.crs or ds.transform != transform or
                ds.width != baseline.width or ds.height != baseline.height):
                reject(f'{label}: mismatched grid; resampling is M1 responsibility')
            kind = rasters[label][1]
            if kind == 'power' and ds.dtypes[0] != 'float32':
                reject(f'{label}: expected float32 linear power, got {ds.dtypes[0]}')
            if kind in ('valid', 'shadow') and ds.dtypes[0] != 'uint8':
                reject(f'{label}: expected uint8 mask, got {ds.dtypes[0]}')
        for k, actual in [('width', baseline.width), ('height', baseline.height)]:
            if grid.get(k) != actual:
                reject(f'grid.{k}: declared {grid.get(k)!r}, actual {actual}')
        try:
            declared_crs = rasterio.crs.CRS.from_user_input(grid.get('crs'))
            if declared_crs != baseline.crs:
                reject('grid.crs does not match GeoTIFF CRS')
        except Exception:
            reject('grid.crs: invalid CRS')
        try:
            res = float(grid.get('pixel_size_m'))
            if not math.isfinite(res) or res <= 0 or abs(transform.a-res) > 1e-5 or abs(abs(transform.e)-res) > 1e-5:
                reject('grid.pixel_size_m does not match actual pixel spacing')
            if res not in (10.0, 30.0):
                warn('Resolution outside agreed project baseline (10m/30m)')
        except (TypeError, ValueError):
            reject('grid.pixel_size_m: missing/invalid')
        if errors:
            return {'status': 'REJECT', 'errors': errors, 'warnings': warnings, 'info': info}

        total = 0
        valid_count = 0
        invalid_samples = 0
        for row in range(0, baseline.height, tile_size):
            for col in range(0, baseline.width, tile_size):
                window = rasterio.windows.Window(col, row, min(tile_size, baseline.width-col), min(tile_size, baseline.height-row))
                tile = {name: ds.read(1, window=window) for name, ds in opened.items()}
                valid_masks = []
                for side in ('before', 'after'):
                    v = tile[f'{side}_valid']
                    if np.any((v != 0) & (v != 1)):
                        invalid_samples += int(np.count_nonzero((v != 0) & (v != 1)))
                    valid = v == 1
                    if f'{side}_shadow' in tile:
                        s = tile[f'{side}_shadow']
                        if np.any((s != 0) & (s != 1)):
                            invalid_samples += int(np.count_nonzero((s != 0) & (s != 1)))
                        valid &= (s == 0)
                    for pol in pols:
                        layer = tile[f'{side}_{pol}']
                        valid &= np.isfinite(layer) & (layer > 0) & (opened[f'{side}_{pol}'].read_masks(1, window=window) > 0)
                        if np.any(np.isfinite(layer) & (layer < 0)):
                            invalid_samples += int(np.count_nonzero(np.isfinite(layer) & (layer < 0)))
                    valid_masks.append(valid)
                total += tile[f'before_{required_pol}'].size
                valid_count += int(np.count_nonzero(valid_masks[0] & valid_masks[1]))
        if invalid_samples:
            reject(f'{invalid_samples} invalid mask values or negative finite power samples')
        info['pixels_total'] = total
        info['pixels_joint_valid_positive'] = valid_count
        info['joint_usable_fraction'] = round(valid_count / total, 6) if total else 0
        if valid_count == 0:
            reject('No usable shared pixels (after masks and positive finite power)')
        elif valid_count / total < 0.5:
            warn('Less than 50% of grid usable for comparison')
        if not any(f'{side}_shadow' in tile for side in ('before', 'after')):
            warn('Layover/shadow masks not supplied; confidence may be reduced')
    warn('Subpixel residual registration has NOT been measured; T04 QA remains required')
    info['sensor'] = sensor
    info['provenance_verified_against_original_sensor_product'] = False
    if sensor == 'NISAR':
        warn('NISAR GCOV diagonal HHHH power is NOT Sentinel-1 VV; no cross-sensor calibration is claimed')
    info['registration_residual_verified'] = False
    return {'status': 'REJECT' if errors else 'WARNING' if warnings else 'PASS',
            'errors': errors, 'warnings': warnings, 'info': info}


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate SPECTRA-SAR M1→M2 real RTC input pair')
    parser.add_argument('pair_dir', help='Directory with manifest.json and GeoTIFFs')
    parser.add_argument('--output', help='Write JSON report to this path')
    args = parser.parse_args()
    try:
        report = inspect_pair(args.pair_dir)
    except (ValueError, TypeError, OSError, rasterio.errors.RasterioError) as exc:
        report = {'status': 'REJECT', 'errors': [f'Input processing failed: {exc}'], 'warnings': [], 'info': {}}
    printed = json.dumps(report, indent=2, ensure_ascii=False)
    print(printed)
    if args.output:
        Path(args.output).write_text(printed + '\n', encoding='utf-8')
    return {'PASS': 0, 'WARNING': 2, 'REJECT': 3}[report['status']]


if __name__ == '__main__':
    sys.exit(main())
