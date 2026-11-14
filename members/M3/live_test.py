#!/usr/bin/env python3
"""Genuine data acquisition and validated M3 integration; never synthesize hazard footprints."""
import argparse, json, subprocess, sys, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser(description='M3 live source check, optionally run T03-T08 if verified M2 footprint provided')
 p.add_argument('--aoi',type=Path,required=True,help='Real EPSG:4326 AOI GeoJSON')
 p.add_argument('--year',type=int,default=2025)
 p.add_argument('--resolution',choices=['100m','1km'],default='100m')
 p.add_argument('--out',type=Path,default=Path('live_results'))
 p.add_argument('--hazard',type=Path,help='Real M2 georeferenced hazard/change footprint (no test geometry)')
 p.add_argument('--hazard-provenance',help='Real M2 product, acquisition dates and validation evidence')
 p.add_argument('--hazard-type',default='unknown',choices=['unknown','flood','wildfire','other'])
 p.add_argument('--evidence-status',default='UNVERIFIED')
 p.add_argument('--sar-confidence',type=float)
 p.add_argument('--approve-qa-warning',action='store_true')
 args=p.parse_args()
 if not args.aoi.is_file():p.error('AOI file not found')
 if args.hazard and (not args.hazard.is_file() or not args.hazard_provenance):p.error('Real hazard file and provenance both required')
 out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);raw=out/'raw';raw.mkdir(exist_ok=True)
 cmd=[sys.executable,str(ROOT/'T02/data_fetcher.py'),'--aoi',str(args.aoi.resolve()),'--year',str(args.year),'--resolution',args.resolution,'--out',str(raw)]
 print('T02: downloading OSM + WorldPop from public providers...',flush=True)
 result=subprocess.run(cmd,cwd=ROOT/'T02')
 manifest_file=raw/'source_manifest.json'
 if result.returncode:
  print('T02 FAILED; inspect source_manifest.json; no downstream processing performed.',file=sys.stderr);return 2
 manifest=json.loads(manifest_file.read_text())
 for s in ('osm','worldpop'):
  if manifest['sources'][s]['status']!='downloaded':raise RuntimeError(s+' not downloaded')
 paths={'aoi':str(args.aoi.resolve()),'osm':str(raw/'osm_features.geojson'),
        'population':str(raw/f'worldpop_population_{args.year}_{args.resolution}.tif')}
 for k,path in paths.items():
  if not Path(path).is_file():raise RuntimeError(f'Missing {k}: {path}')
 (out/'data_inventory.json').write_text(json.dumps({'files':{k:{'path':v,'sha256':sha(v),'size':Path(v).stat().st_size} for k,v in paths.items()},'source_manifest':str(manifest_file),'status':'LIVE_SOURCE_FILES_DOWNLOADED_NOT_YET_VALIDATED'},indent=2)+'\n')
 print('T02 DOWNLOAD PASS; inventory saved.',flush=True)
 if args.hazard is None:
  print('STOP: No real M2 hazard/change footprint supplied; T03-T08 not run.')
  return 0
 cfg={**paths,'hazard':str(args.hazard.resolve()),'hazard_provenance':args.hazard_provenance,
      'population_provenance':f'WorldPop Global2 {args.year} {args.resolution}; URL: https://api.worldpop.org/v3/raster; sha256: {sha(paths["population"])}',
      'population_unit':'count_per_pixel','source_manifest':str(manifest_file),
      'hazard_type':args.hazard_type,'evidence_status':args.evidence_status,
      'sar_confidence':args.sar_confidence,'approve_qa_warning':args.approve_qa_warning}
 config=out/'live_config.json'; config.write_text(json.dumps(cfg,indent=2)+'\n')
 print('T03-T08: attempting real-data pipeline...',flush=True)
 proc=subprocess.run([sys.executable,str(ROOT/'T09/pipeline.py'),'--config',str(config),'--out',str(out/'analysis')],cwd=ROOT/'T09')
 if proc.returncode:print('Pipeline failed closed. Inspect QA and error details.',file=sys.stderr)
 return proc.returncode
if __name__=='__main__':sys.exit(main())
