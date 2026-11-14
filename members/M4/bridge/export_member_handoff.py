#!/usr/bin/env python3
"""Generate a minimal actual-bytes handoff, from the root folder of a team member."""
import argparse, hashlib, json, os, pathlib, sys
p=argparse.ArgumentParser();p.add_argument('--member',required=True,choices=['M1','M2','M3','M5','M6']);p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('.'));p.add_argument('--output',type=pathlib.Path,default=pathlib.Path('handoff.json'));a=p.parse_args()
root=a.root.resolve();output=a.output.resolve();files=[]
for f in sorted(root.rglob('*')):
    if not f.is_file() or f.is_symlink() or output==f.resolve():continue
    rel=f.relative_to(root)
    if any(x.startswith('.') or x in ('__pycache__','node_modules','venv','secrets','credentials','dist') for x in rel.parts):continue
    if f.suffix.lower() not in ('.json','.geojson','.tif','.tiff','.csv','.parquet','.nc','.npz','.npy','.md','.yaml','.yml','.png','.py'):continue
    if f.stat().st_size>250*1024*1024:continue
    h=hashlib.sha256()
    with f.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    files.append({'path':rel.as_posix(),'sha256':h.hexdigest(),'size_bytes':f.stat().st_size})
if not files:sys.exit('No eligible files found; cannot create an empty handoff')
doc={'schema_version':'1.0','member':a.member,'artifacts':files,'source_details':{'note':'Untrusted self-declared byte manifest; source provenance must be independently verified'}}
output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(doc,indent=2)+'\n');print(f'{len(files)} files recorded in {output}')
