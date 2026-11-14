"""Run offline quality gates in isolated working directories.

This intentionally does NOT start Docker, call remote endpoints or download SAR scenes.
Run at repository root with: python M6/Phase-1/T08/scripts/run_offline_tests.py --repo-root . --require-all
"""
import argparse
from pathlib import Path
import subprocess
import sys

TASKS = ('T02', 'T03', 'T04', 'T05', 'T06', 'T07')


def task_dir(repo: Path, name: str) -> Path:
    return repo / 'M6' / 'Phase-1' / name


def commands_for(name: str):
    if name in ('T02', 'T03', 'T04', 'T06'):
        return [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']
    return [sys.executable, '-m', 'pytest', '-q', '-ra', 'tests']


def run_all(repo: Path, require_all: bool):
    report = ['# SPECTRA-SAR CI — offline verification', '',
              '| Module | Result | Note |', '|---|---|---|']
    failed = False
    ran = 0
    for task in TASKS:
        directory = task_dir(repo, task)
        tests = directory / 'tests'
        if not tests.is_dir():
            status = 'FAIL' if require_all else 'NOT INSTALLED'
            report.append(f'| {task} | {status} | Missing tests directory |')
            failed = failed or require_all
            continue
        command = commands_for(task)
        print(f'\n=== {task}: {" ".join(command)} ===', flush=True)
        result = subprocess.run(command, cwd=directory, check=False)
        ran += 1
        status = 'PASS' if result.returncode == 0 else 'FAIL'
        report.append(f'| {task} | {status} | Exit code {result.returncode} |')
        failed = failed or result.returncode != 0
    if ran == 0:
        failed = True
        report.append('| All | FAIL | No test suites discovered |')
    report += ['', 'Live API, PostgreSQL, Docker and real Sentinel-1 scientific validation are **not** covered by this offline gate.', '']
    report_path = repo / 'spectra-ci-results.md'
    report_path.write_text('\n'.join(report), encoding='utf-8')
    print('\n' + '\n'.join(report), flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--repo-root', default='.')
    p.add_argument('--require-all', action='store_true')
    args = p.parse_args()
    sys.exit(run_all(Path(args.repo_root).resolve(), args.require_all))
