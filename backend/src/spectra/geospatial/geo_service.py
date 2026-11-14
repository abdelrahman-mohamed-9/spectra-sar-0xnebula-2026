"""PostGIS-backed spatial queries with parameterized SQLAlchemy expressions."""
from __future__ import annotations
import json
from uuid import UUID
from sqlalchemy import select, func, cast, Float
from sqlalchemy.orm import Session
from spectra.persistence import models
from spectra.geospatial.geojson_converter import feature_from_postgis


def scene_footprint(db: Session, scene_id: UUID) -> dict | None:
    row = db.execute(select(models.SarScene.id,
            func.ST_AsGeoJSON(models.SarScene.footprint).label('geom'))
            .where(models.SarScene.id == scene_id)).one_or_none()
    if row is None or row.geom is None:
        return None
    return feature_from_postgis(row.geom, feature_id=str(row.id), properties={'resource_type': 'sar_scene'})


def impact_footprint(db: Session, impact_id: UUID) -> dict | None:
    row = db.execute(select(models.ImpactAssessment.id,
            models.ImpactAssessment.risk_level,
            func.ST_AsGeoJSON(models.ImpactAssessment.affected_area).label('geom'))
            .where(models.ImpactAssessment.id == impact_id)).one_or_none()
    if row is None or row.geom is None:
        return None
    return feature_from_postgis(row.geom, feature_id=str(row.id),
                                properties={'resource_type': 'impact_assessment', 'risk_level': row.risk_level})


def query_scenes_in_bbox(db: Session, bbox: tuple[float, float, float, float], *, limit: int = 50, offset: int = 0) -> dict:
    left, bottom, right, top = bbox
    envelope = func.ST_MakeEnvelope(left, bottom, right, top, 4326)
    q = (select(models.SarScene.id, models.SarScene.provider_item_id,
                func.ST_AsGeoJSON(models.SarScene.footprint).label('geom'))
         .where(models.SarScene.footprint.is_not(None))
         .where(func.ST_Intersects(models.SarScene.footprint, envelope))
         .order_by(models.SarScene.acquisition_start.desc(), models.SarScene.id)
         .limit(limit).offset(offset))
    features = [feature_from_postgis(row.geom, feature_id=str(row.id),
                  properties={'provider_item_id': row.provider_item_id}) for row in db.execute(q)]
    return {'type': 'FeatureCollection', 'features': features}


def query_impacts_in_bbox(db: Session, bbox: tuple[float, float, float, float], *, project_id: UUID, limit: int = 50, offset: int = 0) -> dict:
    left, bottom, right, top = bbox
    envelope = func.ST_MakeEnvelope(left, bottom, right, top, 4326)
    q = (select(models.ImpactAssessment.id, models.ImpactAssessment.risk_level,
                func.ST_AsGeoJSON(models.ImpactAssessment.affected_area).label('geom'))
         .join(models.ChangeResult, models.ChangeResult.id == models.ImpactAssessment.change_result_id)
         .join(models.ScenePair, models.ScenePair.id == models.ChangeResult.scene_pair_id)
         .where(models.ScenePair.project_id == project_id)
         .where(models.ImpactAssessment.affected_area.is_not(None))
         .where(func.ST_Intersects(models.ImpactAssessment.affected_area, envelope))
         .order_by(models.ImpactAssessment.id)
         .limit(limit).offset(offset))
    features = [feature_from_postgis(row.geom, feature_id=str(row.id),
                  properties={'risk_level': row.risk_level}) for row in db.execute(q)]
    return {'type': 'FeatureCollection', 'features': features}
