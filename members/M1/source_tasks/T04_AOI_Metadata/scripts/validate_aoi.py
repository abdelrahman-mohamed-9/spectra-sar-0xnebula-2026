#!/usr/bin/env python3
"""Validate T04 handoff; stdlib only, never claim physical hazard detection."""
from pathlib import Path
import json,math,sys
BASE=Path(__file__).resolve().parents[1]

def main():
  meta=json.loads((BASE/'metadata/metadata.json').read_text())
  assert meta['validity']['no_direct_raster_download_or_processing_performed'] is True
  for name, key in [('flood','flood'),('glacier','glacier')]:
    d=json.loads((BASE/f'aoi/{name}-aoi.geojson').read_text())
    assert d['type']=='FeatureCollection' and len(d['features'])==1
    feature=d['features'][0]; assert feature['properties']['authoritative_boundary'] is False
    coords=feature['geometry']['coordinates'][0]
    assert feature['geometry']['type']=='Polygon' and len(coords)==5 and coords[0]==coords[-1]
    assert all(len(c)==2 and all(math.isfinite(v) for v in c) and -180 <= c[0] <=180 and -90 <=c[1]<=90 for c in coords)
    bounds=meta['discovery_aoi'][key]
    expected=[[bounds[0],bounds[1]],[bounds[2],bounds[1]],[bounds[2],bounds[3]],[bounds[0],bounds[3]],[bounds[0],bounds[1]]]
    assert coords == expected, f'{key} rectangle differs from published CMR search area'
    print(f'PASS {name}: bbox {bounds}, EPSG:4326 lon/lat; provisional only')
  g=meta['flood']; before=g['before']; after=g['after']
  for field in ('track','direction','frame','mode','polarization_code'):
    assert before['name_metadata'][field]==after['name_metadata'][field],field
  assert before['maturity']==after['maturity']=='PROVISIONAL'
  assert before['acquisition_start_utc'] < after['acquisition_start_utc']
  assert meta['glacier']['primary']['product']=='GOFF'
  assert g['flood_inundation_confirmed'] is False
  handoff=json.loads((BASE/'metadata/handoff-m2-m5.json').read_text())
  assert handoff['status']=='DISCOVERY_ONLY_AWAITING_REAL_RASTERS'
  assert handoff['gcov']['local_file_paths']['before'] is None
  print('PASS CMR scene pairing and safe provenance flags')
  print('T04_METADATA_READY — NOT T03_SCIENCE_APPROVED')
  return 0
if __name__=='__main__':
 try: sys.exit(main())
 except (AssertionError, ValueError, KeyError) as e:
  print(f'FAILED T04 VALIDATION: {e}',file=sys.stderr);sys.exit(1)
