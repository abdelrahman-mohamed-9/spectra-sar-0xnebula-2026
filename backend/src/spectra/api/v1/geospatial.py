"""Internal geospatial routes; all queries require the T06 service key."""
from __future__ import annotations
import math
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from spectra.api.v1.security import require_service_key
from spectra.persistence.database import get_db
from spectra.geospatial import geo_service

router = APIRouter(prefix='/geospatial', tags=['Geospatial'], dependencies=[Depends(require_service_key)])


def validate_bbox(value: str) -> tuple[float,float,float,float]:
    try:
        parts = value.split(',')
        if len(parts) != 4: raise ValueError()
        bounds = tuple(float(p) for p in parts)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422,detail='bbox must be minLon,minLat,maxLon,maxLat') from None
    a,b,c,d=bounds
    if not all(math.isfinite(x) for x in bounds) or not (-180 <= a < c <= 180 and -90 <= b < d <= 90):
        raise HTTPException(status_code=422, detail='Invalid WGS84 bbox; antimeridian-crossing boxes need two queries')
    return bounds


@router.get('/scenes/within')
def scenes_within(bbox: str = Query(...), limit: int = Query(50,ge=1,le=100),
                  offset: int = Query(0,ge=0), db: Session = Depends(get_db)):
    return geo_service.query_scenes_in_bbox(db, validate_bbox(bbox), limit=limit, offset=offset)


@router.get('/impacts/within')
def impacts_within(project_id: UUID, bbox: str = Query(...), limit: int = Query(50,ge=1,le=100),
                   offset: int = Query(0,ge=0), db: Session = Depends(get_db)):
    return geo_service.query_impacts_in_bbox(db, validate_bbox(bbox), project_id=project_id, limit=limit, offset=offset)


@router.get('/scenes/{scene_id}/footprint')
def get_scene_footprint(scene_id: UUID, db: Session = Depends(get_db)):
    value = geo_service.scene_footprint(db,scene_id)
    if value is None: raise HTTPException(status_code=404,detail='Footprint not found')
    return value


@router.get('/impacts/{impact_id}/footprint')
def get_impact_footprint(impact_id: UUID, db: Session = Depends(get_db)):
    value = geo_service.impact_footprint(db,impact_id)
    if value is None: raise HTTPException(status_code=404,detail='Footprint not found')
    return value
