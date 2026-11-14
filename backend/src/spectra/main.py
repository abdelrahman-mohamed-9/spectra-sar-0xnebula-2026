from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from spectra.api.health import router as health_router
from spectra.api.database_health import router as database_health_router
from spectra.api.v1.router import router as v1_router
from spectra.core.config import get_settings
from spectra.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(get_settings())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan,
                  description="Backend foundation with migration-aware database health. Authenticated scientific data APIs included; Celery dispatch available; real scientific handlers require integration.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Content-Type", "Authorization", "X-Request-ID"])

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if 1 <= len(incoming) <= 128 and all(ch.isalnum() or ch in "-_." for ch in incoming) else str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    app.include_router(health_router)
    app.include_router(database_health_router)
    app.include_router(v1_router, prefix=settings.api_prefix)
    # Unified local processing routes are enabled by the monorepo launcher.
    try:
        from phase1.api import router as phase1_router
    except ModuleNotFoundError as exc:
        if exc.name != "phase1": raise
    else:
        app.include_router(phase1_router)
    return app


app = create_app()
