#!/usr/bin/env python3
"""Extract **trusted** M6 task ZIPs T01–T08 into canonical repo paths.

Reject unexpected paths, symlink ZIP entries, duplicates and overwrites.
This script should only be run on archives obtained from the team.
"""
import argparse
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import zipfile

TASKS = list(range(1,9))

def find_archive(folder, n):
    suffix=f'{n:02d}'
    fixed=folder / f'SPECTRA-SAR_M6_Phase1_T{suffix}_FIXED.zip'
    regular=folder / f'SPECTRA-SAR_M6_Phase1_T{suffix}.zip'
    choice=fixed if n==2 and fixed.is_file() else regular
    if not choice.is_file(): raise ValueError(f'Missing T{suffix} ZIP in {folder}')
    return choice

def normalize(name,n):
    prefix=f'T{n:02d}/'
    for leader in (f'SPECTRA-SAR/M6/Phase-1/{prefix}',prefix):
        if name.startswith(leader):
            return name[len(leader):]
    if name in (f'T{n:02d}/',f'SPECTRA-SAR/M6/Phase-1/{prefix}'):
        return ''
    raise ValueError(f'Unexpected archive entry for T{n:02d}: {name}')

def plan(folder,repo):
    instructions=[]; seen=set()
    for n in TASKS:
        archive=find_archive(folder,n)
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                name=info.filename.replace('\\','/')
                if info.is_dir(): continue
                if stat.S_IFMT(info.external_attr >> 16)==stat.S_IFLNK:
                    raise ValueError(f'Symlinks are unsupported: {name}')
                relative=normalize(name,n)
                parts=PurePosixPath(relative).parts
                if not parts or any(p in ('..','.') for p in parts) or relative.startswith('/'):
                    raise ValueError(f'Unsafe member path: {name}')
                dest=repo/'M6'/'Phase-1'/f'T{n:02d}'/Path(*parts)
                if dest in seen or dest.exists(): raise ValueError(f'Duplicate or already existing destination: {dest}')
                seen.add(dest)
                instructions.append((archive,info.filename,dest))
    return instructions

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archives',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--dry-run',action='store_true')
    args=p.parse_args()
    try:
        steps=plan(args.archives.resolve(),args.output.resolve())
        print(f'Validated {len(steps)} files from T01–T08')
        for archive,member,dest in steps:
            if args.dry_run: print(f'{archive.name}:{member} -> {dest}')
            else:
                dest.parent.mkdir(parents=True,exist_ok=True)
                with zipfile.ZipFile(archive) as z, z.open(member) as source, open(dest,'xb') as target:
                    shutil.copyfileobj(source,target)
        print('DRY RUN; no writes' if args.dry_run else 'Extracted safely; copy T09 and T08 CI workflow separately')
    except (ValueError,zipfile.BadZipFile,OSError) as e:
        print(f'ERROR: {e}',file=sys.stderr); return 1
    return 0

if __name__=='__main__': sys.exit(main())
