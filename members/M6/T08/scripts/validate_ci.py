"""Offline sanity check of workflow structure and required files."""
import argparse
from pathlib import Path
import sys
import yaml


def validate(repo: Path, require_all=False):
    workflow = repo / '.github' / 'workflows' / 'ci.yml'
    runner = repo / 'M6' / 'Phase-1' / 'T08' / 'scripts' / 'run_offline_tests.py'
    requirements = repo / 'M6' / 'Phase-1' / 'T08' / 'requirements-ci.txt'
    missing = [str(p.relative_to(repo)) for p in (workflow, runner, requirements) if not p.is_file()]
    if missing:
        return ['Required files missing: ' + ', '.join(missing)]
    # PyYAML 1.1 treats the key `on` as boolean True, so accept either form.
    data = yaml.safe_load(workflow.read_text(encoding='utf-8'))
    errors = []
    events = data.get('on', data.get(True))
    if not isinstance(events, dict) or 'pull_request' not in events or 'push' not in events:
        errors.append('Workflow must run for pull_request and push')
    if data.get('permissions') != {'contents': 'read'}:
        errors.append('Workflow permissions must be read-only')
    steps = data.get('jobs', {}).get('offline-qa', {}).get('steps', [])
    if not any('run_offline_tests.py' in str(s.get('run', '')) for s in steps):
        errors.append('Offline runner step not found')
    if require_all:
        for name in ('T02','T03','T04','T05','T06','T07'):
            if not (repo / 'M6' / 'Phase-1' / name / 'tests').is_dir():
                errors.append(f'{name}: tests directory missing; unpack or commit this task')
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--repo-root', default='.')
    p.add_argument('--require-all', action='store_true')
    args = p.parse_args()
    issues = validate(Path(args.repo_root).resolve(), args.require_all)
    print('CI config VALID' if not issues else 'CI config INVALID: ' + '; '.join(issues))
    sys.exit(bool(issues))
