from fastapi import APIRouter
from spectra.api.v1.resources import router as resources_router
from spectra.api.v1.geospatial import router as geospatial_router

from spectra.api.v1.jobs import router as jobs_router

router = APIRouter()

@router.get('/', tags=['service'])
def api_index() -> dict[str,str]:
    return {'service':'spectra-sar','version':'v1','status':'scaffold'}

router.include_router(resources_router)
router.include_router(geospatial_router)

router.include_router(jobs_router)

from spectra.api.v1.storage import router as storage_router
router.include_router(storage_router)

from spectra.api.v1.auth import router as auth_router
router.include_router(auth_router)
