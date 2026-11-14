from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def now():
    return datetime.now(timezone.utc).isoformat()

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    os.replace(tmp, path)

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def safe(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Expected relative path under allowed root')
    p = (root / rel).resolve()
    if not p.is_relative_to(root):
        raise ValueError('Path escapes allowed root')
    return p

def command(args, log, allowed=(0,), timeout=1800):
    result = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True, timeout=timeout)
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    Path(log).write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
    if result.returncode not in allowed:
        raise RuntimeError(f'{Path(str(args[0])).name} exited {result.returncode}; see {Path(log).name}')
    return result
