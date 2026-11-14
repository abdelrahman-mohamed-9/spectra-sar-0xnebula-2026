"""One app: original Phase 1 M5 routes, Phase 2 jobs, and local dashboard."""
import os
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import build_router, local_identity
from .jobs import Jobs

WEB = Path(__file__).with_name('web')
MISSION = Path(__file__).resolve().parents[1] / 'judge-demo'


def attach_dashboard(app):
    app.mount('/assets', StaticFiles(directory=WEB), name='spectra-assets')
    if (MISSION / 'index.html').exists():
        app.mount('/mission', StaticFiles(directory=MISSION, html=True), name='spectra-offline-mission')
    @app.get('/', include_in_schema=False)
    def dashboard():
        return FileResponse(WEB/'index.html', headers={
            'Cache-Control':'no-store',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
            'X-Content-Type-Options':'nosniff'})
    return app


def create_local_app():
    from spectra.main import create_app
    state=os.environ.get('SPECTRA_PHASE2_STATE')
    if not state: raise ValueError('Set SPECTRA_PHASE2_STATE')
    app=create_app()
    app.title='SPECTRA SAR · Phase 1 + Phase 2 + Phase 3'
    app.version='3.4.0'
    app.description='Integrated exploratory SAR workspace. Original Phase 1 routes use their service key; Phase 2 local routes use the operator token. No scientific approval is implied.'
    app.include_router(build_router(Jobs(state), local_identity(os.environ.get('SPECTRA_PHASE2_TOKEN'))))
    return attach_dashboard(app)
