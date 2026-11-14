"""Mount Phase 2 on the team's existing M5 app and reuse its JWT identity."""

import os
from typing import Annotated

from fastapi import Depends
from spectra.main import create_app
from spectra.persistence.models import User
from spectra.security.auth import current_user

from .api import build_router
from .jobs import Jobs


def owner(user: Annotated[User, Depends(current_user)]):
    return user.id


def create_integrated_app():
    state = os.environ.get("SPECTRA_PHASE2_STATE")
    if not state:
        raise ValueError("Configure SPECTRA_PHASE2_STATE")
    app = create_app()
    app.include_router(build_router(Jobs(state), owner))
    from .application import attach_dashboard
    return attach_dashboard(app)
