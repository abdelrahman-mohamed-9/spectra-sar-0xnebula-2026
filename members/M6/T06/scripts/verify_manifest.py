"""CLI: python scripts/verify_manifest.py manifest.json --root /trusted/artifacts"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from provenance import validate_manifest, verify_local_artifacts

def main():
    p = argparse.ArgumentParser()
    p.add_argument('manifest', type=Path)
    p.add_argument('--root', required=True, type=Path, help='Trusted local artifact root')
    args = p.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        validate_manifest(manifest)
        result = verify_local_artifacts(manifest, root=args.root)
        print(json.dumps(result, indent=2))
        if not result['all_artifacts_verified']:
            print('WARNING: remote objects not verified; not a full integrity pass', file=sys.stderr)
            return 2
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
