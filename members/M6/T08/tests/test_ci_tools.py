from pathlib import Path
import importlib.util
import subprocess
import sys

def load(name, filepath):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ROOT = Path(__file__).resolve().parents[1]
RUN = load('offline_runner', ROOT / 'scripts/run_offline_tests.py')
VAL = load('ci_validator', ROOT / 'scripts/validate_ci.py')


def test_task_paths(tmp_path):
    assert RUN.task_dir(tmp_path, 'T07') == tmp_path / 'M6/Phase-1/T07'


def test_runner_never_silently_passes_empty_suite(tmp_path):
    assert RUN.run_all(tmp_path, False) == 1
    assert 'No test suites discovered' in (tmp_path / 'spectra-ci-results.md').read_text()


def test_require_all_fails_when_modules_missing(tmp_path):
    assert RUN.run_all(tmp_path, True) == 1
    assert '| T02 | FAIL |' in (tmp_path / 'spectra-ci-results.md').read_text()


def test_runner_passes_real_unittest_directory(tmp_path):
    p = tmp_path / 'M6/Phase-1/T02/tests'
    p.mkdir(parents=True)
    (p/'test_smoke.py').write_text('import unittest\nclass Smoke(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
    assert RUN.run_all(tmp_path, False) == 0
    assert '| T02 | PASS |' in (tmp_path/'spectra-ci-results.md').read_text()


def test_validator_detects_missing_files(tmp_path):
    assert VAL.validate(tmp_path)


def test_repo_template_validates_in_staging(tmp_path):
    # CI zip itself contains a nested repository-ready payload; stage it in canonical place.
    import shutil
    shutil.copytree(ROOT, tmp_path/'M6/Phase-1/T08')
    (tmp_path/'.github/workflows').mkdir(parents=True)
    shutil.copy(ROOT/'.github/workflows/ci.yml', tmp_path/'.github/workflows/ci.yml')
    assert VAL.validate(tmp_path, False) == []
    assert any('T02' in err for err in VAL.validate(tmp_path, True))
