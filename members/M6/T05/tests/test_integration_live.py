"""Requires an already-running canonical M5 service; does not create runs or fetch satellite data."""
import os
import requests
import pytest

@pytest.mark.integration
def test_backend_readiness():
    base=os.environ.get('SPECTRA_API_BASE_URL')
    if not base: pytest.skip('Set SPECTRA_API_BASE_URL to the running backend URL')
    response=requests.get(base.rstrip('/')+'/health/ready',timeout=5)
    assert response.status_code==200, response.text[:300]
    assert response.json()['status']=='ready'

@pytest.mark.integration
def test_unauthorized_run_rejected():
    base=os.environ.get('SPECTRA_API_BASE_URL')
    if not base: pytest.skip('Set SPECTRA_API_BASE_URL to the running backend URL')
    # Read-only security check. Actual backend must enforce auth on this route.
    response=requests.get(base.rstrip('/')+'/api/v1/phase1/runs/00000000-0000-4000-8000-000000000001',timeout=5)
    assert response.status_code==401
