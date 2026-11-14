from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def pytest_addoption(parser):
    parser.addoption('--run-integration',action='store_true',default=False,help='enable tests against running backend')
    parser.addoption('--run-database',action='store_true',default=False,help='enable tests against real PostgreSQL')

def pytest_collection_modifyitems(config,items):
    flags={'integration':'--run-integration','database':'--run-database'}
    for item in items:
        for marker,flag in flags.items():
            if marker in item.keywords and not config.getoption(flag):
                item.add_marker(pytest.mark.skip(reason=f'requires explicit {flag} and live service'))
