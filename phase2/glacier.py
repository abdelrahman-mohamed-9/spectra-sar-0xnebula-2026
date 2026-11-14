"""Screen geocoded displacement components; never infer surface velocity."""
import hashlib
import io
import json
import zipfile
from datetime import datetime

import numpy as np
from rasterio.io import MemoryFile
from rasterio.warp import transform_bounds
from scipy.ndimage import median_filter
from pyproj import Transformer

MAX_BYTES = 32 * 1024 * 1024
LAYERS = ('along_track', 'slant_range', 'snr', 'glacier_mask')


def analyze_bundle(payload, aoi):
    if len(payload) > MAX_BYTES:
        raise ValueError('Bundle exceeds 32 MB; provide a cropped bundle')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        expected = {'manifest.json', *(name+'.tif' for name in LAYERS)}
        if len(entries) != len(expected) or {x.filename for x in entries} != expected:
            raise ValueError('Bundle must contain manifest.json and exactly four required GeoTIFFs at its root')
        if sum(x.file_size for x in entries) > 128*1024*1024:
            raise ValueError('Expanded bundle exceeds 128 MB')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('units') != 'meters' or manifest.get('offset_convention') != 'secondary_minus_reference':
            raise ValueError('Offsets must be meters with secondary_minus_reference convention')
        for key in ('source_product', 'source_url', 'glacier_source'):
            if not isinstance(manifest.get(key), str) or not manifest[key].strip():
                raise ValueError('Missing source metadata: '+key)
        dates = [datetime.fromisoformat(manifest[k].replace('Z','+00:00')) for k in ('reference_time','secondary_time')]
        if any(d.tzinfo is None for d in dates):
            raise ValueError('Acquisition timestamps must include timezone')
        days = (dates[1]-dates[0]).total_seconds()/86400
        if days <= 0:
            raise ValueError('Secondary acquisition must follow reference acquisition')
        arrays, valid, receipts = {}, None, {}
        grid = None
        for name in LAYERS:
            raw = archive.read(name+'.tif')
            receipts[name+'.tif'] = hashlib.sha256(raw).hexdigest()
            with MemoryFile(raw) as memory, memory.open() as raster:
                if raster.driver != 'GTiff' or raster.count != 1 or not raster.crs or raster.width*raster.height > 1_000_000:
                    raise ValueError('Use single-band georeferenced GeoTIFFs with at most one million cells')
                if grid is None:
                    grid = (raster.crs, raster.transform, raster.shape)
                    bounds = transform_bounds(raster.crs,'EPSG:4326',*raster.bounds)
                    # Do not attach unrelated-area displacement to this SAR run.
                    if min(bounds[2],aoi[2]) <= max(bounds[0],aoi[0]) or min(bounds[3],aoi[3]) <= max(bounds[1],aoi[1]):
                        raise ValueError('Displacement coverage does not overlap this analysis area')
                elif grid != (raster.crs, raster.transform, raster.shape):
                    raise ValueError('All four layers must use the same CRS, transform and dimensions')
                values = raster.read(1, masked=True)
                arrays[name] = values.filled(np.nan).astype(float) if values.dtype.kind == 'f' else values.astype(float).filled(np.nan)
                layer_valid = ~np.ma.getmaskarray(values) & np.isfinite(arrays[name])
                valid = layer_valid if valid is None else valid & layer_valid
        if not np.all(np.isin(arrays['glacier_mask'][np.isfinite(arrays['glacier_mask'])],[0,1])):
            raise ValueError('Glacier mask must contain 0 outside and 1 inside glacier boundaries')
        yy, xx = np.indices(grid[2], dtype=float)
        xx += 0.5
        yy += 0.5
        affine = grid[1]
        longitude, latitude = Transformer.from_crs(grid[0], 'EPSG:4326', always_xy=True).transform(
            affine.a*xx + affine.b*yy + affine.c, affine.d*xx + affine.e*yy + affine.f)
        within_aoi = (longitude >= aoi[0]) & (longitude <= aoi[2]) & (latitude >= aoi[1]) & (latitude <= aoi[3])
        inside = valid & within_aoi & (arrays['glacier_mask'] == 1)
        accepted = inside & (arrays['snr'] >= 5)
        initial = int(accepted.sum())
        # Median neighborhood residual screening; thresholds are exploratory.
        for name in ('along_track','slant_range'):
            values = arrays[name]
            fill = float(np.median(values[accepted])) if accepted.any() else 0
            residual = np.abs(values - median_filter(np.where(accepted,values,fill),size=3))
            reference = residual[accepted]
            cutoff = max(0.1, float(np.median(reference) + 3*1.4826*np.median(np.abs(reference-np.median(reference))))) if len(reference) else 0.1
            accepted &= residual <= cutoff
        components = {}
        for name in ('along_track','slant_range'):
            values = arrays[name][accepted]
            components[name] = {'median_displacement_m':float(np.median(values)) if values.size else None,
                'median_rate_m_per_day':float(np.median(values)/days) if values.size else None,
                'p10_rate_m_per_day':float(np.percentile(values,10)/days) if values.size else None,
                'p90_rate_m_per_day':float(np.percentile(values,90)/days) if values.size else None}
        receipts['manifest.json'] = hashlib.sha256(archive.read('manifest.json')).hexdigest()
    return {'schema_version':'1.0','status':'EXPLORATORY' if accepted.any() else 'NO_VALID_MEASUREMENTS',
        'source':manifest,'elapsed_days':days,'bounds_wgs84':list(bounds),
        'valid_glacier_cells':int(inside.sum()),'snr_accepted_cells':initial,'retained_cells':int(accepted.sum()),
        'components':components,'source_sha256':hashlib.sha256(payload).hexdigest(),'file_hashes':receipts,
        'policy':{'snr_minimum':5,'neighborhood':3,'residual_mad_multiplier':3,'residual_floor_m':0.1},
        'limitations':['Radar-coordinate components are not east/north or surface speed.',
            'No stable-ground bias correction or independent velocity validation has been applied.',
            'SNR and residual filters are heuristic; percentiles describe spatial variation, not confidence intervals.',
            'Glacier boundaries and offset units are supplied by the operator; provenance is recorded, not independently certified.']}
