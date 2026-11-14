"""Small generated fixtures test SOFTWARE ONLY, not scientific correctness."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from input_validator import inspect_pair
from data_loader import iter_pair_tiles


def fixture(tmp_path):
    transform = from_origin(500000, 3500000, 30, 30)
    profile = dict(driver='GTiff', height=8, width=8, count=1, crs='EPSG:32636', transform=transform)
    for side in ('before', 'after'):
        for name, data, dtype in [('VV', np.full((8, 8), .23, dtype='float32'), 'float32'),
                                  ('valid_mask', np.ones((8, 8), dtype='uint8'), 'uint8'),
                                  ('layover_shadow', np.zeros((8, 8), dtype='uint8'), 'uint8')]:
            with rasterio.open(tmp_path / f'{side}_{name}.tif', 'w', **profile, dtype=dtype) as dst:
                dst.write(data, 1)
    doc = dict(schema_version='1.0', pair_id='UNIT_TEST_NOT_REAL', source_provider='TEST_ONLY',
               processing_software='TEST_ONLY', processing_version='1', product_type='RTC',
               acquisition_mode='IW', radiometry='gamma0_terrain', units='linear_power',
               polarizations=['VV'], grid=dict(crs='EPSG:32636', width=8, height=8, pixel_size_m=30))
    for side, day in [('before', '01'), ('after', '13')]:
        doc[side] = dict(scene_id=f'UNIT_TEST_{side}', acquired_utc=f'2026-10-{day}T10:00:00Z',
                         relative_orbit=15, orbit_direction='ASCENDING', incidence_angle_deg_summary=36.2,
                         raster_files={'VV': f'{side}_VV.tif'}, valid_mask_file=f'{side}_valid_mask.tif',
                         layover_shadow_mask_file=f'{side}_layover_shadow.tif')
    save(tmp_path, doc)
    return doc


def save(path, doc):
    (path / 'manifest.json').write_text(json.dumps(doc), encoding='utf-8')


def test_valid_data_with_t04_warning(tmp_path):
    fixture(tmp_path)
    report = inspect_pair(tmp_path)
    assert report['status'] == 'WARNING'
    assert report['errors'] == []
    assert report['info']['joint_usable_fraction'] == 1
    tiles = list(iter_pair_tiles(tmp_path, tile_size=5))
    assert len(tiles) == 4
    assert sum(int(t.valid.sum()) for t in tiles) == 64


def test_mismatched_orbit(tmp_path):
    doc = fixture(tmp_path)
    doc['after']['relative_orbit'] = 44
    save(tmp_path, doc)
    assert inspect_pair(tmp_path)['status'] == 'REJECT'


def test_missing_mask(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'after_valid_mask.tif').unlink()
    assert inspect_pair(tmp_path)['status'] == 'REJECT'


def test_misaligned_grid(tmp_path):
    fixture(tmp_path)
    p = tmp_path / 'after_VV.tif'
    with rasterio.open(p) as src:
        data, profile = src.read(1), src.profile
    profile['transform'] = from_origin(500030, 3500000, 30, 30)
    with rasterio.open(p, 'w', **profile) as dst:
        dst.write(data, 1)
    assert any('mismatched grid' in e for e in inspect_pair(tmp_path)['errors'])


def test_bad_units(tmp_path):
    doc = fixture(tmp_path)
    doc['units'] = 'dB'
    save(tmp_path, doc)
    assert inspect_pair(tmp_path)['status'] == 'REJECT'


def test_empty_overlap(tmp_path):
    fixture(tmp_path)
    p = tmp_path / 'after_valid_mask.tif'
    with rasterio.open(p) as src:
        profile = src.profile
    with rasterio.open(p, 'w', **profile) as ds:
        ds.write(np.zeros((8,8), dtype='uint8'), 1)
    assert any('No usable shared pixels' in e for e in inspect_pair(tmp_path)['errors'])


def test_path_traversal(tmp_path):
    doc = fixture(tmp_path)
    doc['before']['raster_files']['VV'] = '../secret.tif'
    save(tmp_path, doc)
    assert inspect_pair(tmp_path)['status'] == 'REJECT'


def test_incidence_warning(tmp_path):
    doc = fixture(tmp_path)
    doc['after']['incidence_angle_deg_summary'] = 40
    save(tmp_path, doc)
    assert any('Incidence angle difference' in w for w in inspect_pair(tmp_path)['warnings'])


def test_negative_power(tmp_path):
    fixture(tmp_path)
    p = tmp_path / 'before_VV.tif'
    with rasterio.open(p) as ds:
        prof = ds.profile
    with rasterio.open(p, 'w', **prof) as ds:
        x = np.full((8,8), .2, dtype='float32')
        x[0,0] = -.1
        ds.write(x,1)
    assert inspect_pair(tmp_path)['status'] == 'REJECT'
