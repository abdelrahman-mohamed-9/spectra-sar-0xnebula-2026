"""Operator-managed, immutable dataset imports from the Phase 1 M1 contract."""
import argparse
import json
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import rasterio
from rasterio.warp import transform_bounds

from .integrity import inventory, safe, verify_inventory
from .m1 import read_scene, scene_files
from .run_m2 import MAX_PIXELS, sha256, write_json

DEFAULT_ID = 'nisar-oct2026'
BUNDLED_SUPPLEMENTS = ('nisar-oct2026-ghsl2025',)
PACKAGE = Path(__file__).resolve().parents[1]


def dataset_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', value):
        raise ValueError('Dataset ID must use 1–64 lowercase letters, digits, hyphens or underscores')
    return value


def resolve(state, name):
    name = dataset_id(name)
    if name == DEFAULT_ID:
        return PACKAGE
    if name in BUNDLED_SUPPLEMENTS:
        candidate = PACKAGE / 'supplemental' / name
        if candidate.is_symlink() or not (candidate / 'catalog.json').is_file():
            raise ValueError('Supplementary dataset is unavailable')
        return candidate
    root = Path(state).resolve() / 'datasets'
    candidate = root / name
    if candidate.is_symlink() or not candidate.is_dir() or not (candidate / 'catalog.json').is_file():
        raise ValueError('Dataset not found')
    if not candidate.resolve().is_relative_to(root):
        raise ValueError('Unsafe dataset directory')
    return candidate


def describe(state, name):
    root = resolve(state, name)
    meta = json.loads((root / 'data/nisar/manifest.json').read_text())
    config = json.loads((root / 'dataset.json').read_text()) if (root / 'dataset.json').exists() else {}
    return {'id': name, 'pair_id': meta['pair_id'], 'sensor': meta.get('sensor'),
            'before': meta['before']['acquired_utc'], 'after': meta['after']['acquired_utc'],
            'polarizations': meta['polarizations'], 'scientific_approval': False,
            'reference_available': (root/'data/reference/labels.tif').is_file(),
            'origin': config.get('origin', 'Supplied Phase 1 NISAR extract'),
            'limitations': meta.get('data_limitations', [])}


def listing(state):
    names = [DEFAULT_ID]
    names += [name for name in BUNDLED_SUPPLEMENTS if (PACKAGE/'supplemental'/name/'catalog.json').is_file()]
    folder = Path(state) / 'datasets'
    if folder.is_dir():
        names += sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.name.startswith('.'))
    result = []
    for name in names:
        try:
            result.append(describe(state, name))
        except (ValueError, KeyError, OSError):
            continue
    return result


def copy_tree(source, dest, maximum=300_000_000):
    total = 0
    source = Path(source).resolve()
    for file in source.rglob('*'):
        if file.is_symlink():
            raise ValueError('Input trees must not contain symbolic links')
        if not file.is_file():
            continue
        total += file.stat().st_size
        if total > maximum:
            raise ValueError('Crop inputs first: source tree exceeds the local 300 MB limit')
        target = dest / file.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)


def register(state, name, pair, geography=None, reference=None, reference_metadata=None):
    from .jobs import Jobs
    dataset_id(name)
    if name == DEFAULT_ID or name in BUNDLED_SUPPLEMENTS:
        raise ValueError('The bundled source is immutable; choose another ID')
    if bool(reference) != bool(reference_metadata):
        raise ValueError('Supply both independent labels and their provenance')
    queue = Jobs(state)
    datasets = queue.root / 'datasets'
    datasets.mkdir(mode=0o700, exist_ok=True)
    dest = datasets / name
    if dest.exists():
        raise ValueError('Dataset already exists; use a new ID to preserve reproducibility')
    pair = Path(pair).resolve()
    manifest = json.loads((pair/'manifest.json').read_text())
    pol = manifest['polarizations'][0]
    for side in ('before', 'after'):
        file = safe(pair, manifest[side]['raster_files'][pol])
        with rasterio.open(file) as ds:
            if ds.width*ds.height > MAX_PIXELS or ds.count != 1 or ds.driver != 'GTiff':
                raise ValueError('Input must be one-band GeoTIFF with at most 2 million pixels')
            if any(Path(dep).resolve().parent != file.parent for dep in ds.files):
                raise ValueError('Raster dependencies must be local')
        read_scene(pair, manifest[side], pol)
    b = safe(pair, manifest['before']['raster_files'][pol])
    a = safe(pair, manifest['after']['raster_files'][pol])
    if sha256(b) == sha256(a):
        raise ValueError('Identical before/after files are not a temporal pair')
    with TemporaryDirectory(prefix='.import-', dir=datasets) as scratch:
        staging = Path(scratch)
        data = staging/'data'
        copy_tree(pair, data/'nisar')
        # Hashes certify this local import only. They are not a NASA signature.
        receipt = data/'nisar/input-provenance.json'
        digests = {side: sha256(safe(pair, manifest[side]['raster_files'][pol])) for side in ('before','after')}
        if receipt.exists():
            existing = json.loads(receipt.read_text())
            if existing.get('input_sha256') != digests:
                raise ValueError('Original import receipt does not match input TIFFs')
        else:
            write_json(receipt, {'input_sha256': digests, 'scientific_approval': False,
                'note': 'Operator import receipt. Original provider authentication not established.'})
        geo = data/'geography'
        if geography:
            copy_tree(geography, geo)
            if not (geo/'geography-source.json').is_file():
                raise ValueError('Geography requires geography-source.json with provenance and coverage')
        else:
            geo.mkdir()
            with rasterio.open(b) as ds:
                bounds = transform_bounds(ds.crs,'EPSG:4326',*ds.bounds, densify_pts=41)
            for filename in ['population.geojson','roads-2.geojson','roads-6.geojson','roads-8.geojson','buildings.geojson']:
                write_json(geo/filename, {'type':'FeatureCollection','features':[]})
            write_json(geo/'geography-source.json', {'query_bbox_wgs84':[bounds[0]-1e-5,bounds[1]-1e-5,bounds[2]+1e-5,bounds[3]+1e-5],
                'population':{'status':'NOT_PROVIDED'}, 'roads':{'status':'NOT_PROVIDED'}, 'buildings':{'status':'NOT_PROVIDED'},
                'note':'No geographic source supplied. Empty collections are placeholders, never observed zero assets.'})
        if reference:
            ref = data/'reference';ref.mkdir()
            shutil.copy2(reference, ref/'labels.tif')
            shutil.copy2(reference_metadata, ref/'provenance.json')
            provenance = json.loads((ref/'provenance.json').read_text())
            if provenance.get('sha256') != sha256(ref/'labels.tif') or provenance.get('pair_id') != manifest['pair_id'] or provenance.get('independent_of_predictions') is not True:
                raise ValueError('Reference provenance must match pair, hash and independence declaration')
        files = [p.relative_to(data).as_posix() for p in data.rglob('*') if p.is_file()]
        pins = inventory(data, files)
        verify_inventory(data, pins)
        write_json(staging/'catalog.json', {name:pins})
        write_json(staging/'dataset.json', {'id':name,'origin':'Operator-imported Phase 1 M1 contract', 'scientific_approval':False})
        staging.rename(dest)
    return describe(state, name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,default=Path('state'))
    parser.add_argument('--id',required=True)
    parser.add_argument('--pair',type=Path,required=True)
    parser.add_argument('--geography',type=Path)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--reference-metadata',type=Path)
    args=parser.parse_args()
    try:
        print(json.dumps(register(args.state,args.id,args.pair,args.geography,args.reference,args.reference_metadata),indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Import rejected: {exc}\n')

if __name__=='__main__': main()
