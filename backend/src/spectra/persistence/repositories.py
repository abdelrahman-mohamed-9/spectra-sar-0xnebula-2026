"""T05 SQLAlchemy repositories. DB validates foreign keys and uniqueness.

Commit transaction in the caller (unit-of-work). No automatic commit per insert.
All writers should use an authenticated project access check when exposed by T06.
"""
from __future__ import annotations
import json
from typing import Generic, TypeVar
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from spectra.persistence import models
from spectra.domain import schemas

M = TypeVar('M')

class Repository(Generic[M]):
    def __init__(self, session: Session, model: type[M]):
        self.session, self.model = session, model

    def get(self, entity_id: UUID) -> M | None:
        return self.session.get(self.model, entity_id)

    def list(self, *, limit: int = 50, offset: int = 0) -> list[M]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError('limit must be 1..100 and offset >= 0')
        return list(self.session.scalars(select(self.model).limit(limit).offset(offset)))

    def add(self, payload) -> M:
        obj = self.model(**payload.model_dump(exclude_none=True))
        self.session.add(obj)
        self.session.flush()
        return obj


def postgis_multipolygon(geometry: schemas.PolygonGeometry):
    """Bind GeoJSON as parameter; convert Polygon to MultiPolygon for column type."""
    geojson=geometry.model_dump(mode='json')
    value=func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geojson)),4326)
    return func.ST_Multi(value)

class SarSceneRepository(Repository[models.SarScene]):
    def __init__(self, session: Session): super().__init__(session, models.SarScene)

    def add(self, payload: schemas.SarSceneCreate) -> models.SarScene:
        values=payload.model_dump(exclude={'footprint'},exclude_none=True)
        if payload.footprint:
            values['footprint']=postgis_multipolygon(payload.footprint)
        obj=models.SarScene(**values)
        self.session.add(obj)
        self.session.flush()
        return obj

    def by_provider_id(self, provider: str, collection: str, item_id: str):
        stmt=select(models.SarScene).where(models.SarScene.provider==provider,
                models.SarScene.collection==collection,
                models.SarScene.provider_item_id==item_id)
        return self.session.scalar(stmt)

class ArtifactRepository(Repository[models.Artifact]):
    def __init__(self,session: Session): super().__init__(session,models.Artifact)

class ScenePairRepository(Repository[models.ScenePair]):
    def __init__(self,session: Session): super().__init__(session,models.ScenePair)

class ProcessingJobRepository(Repository[models.ProcessingJob]):
    def __init__(self,session: Session): super().__init__(session,models.ProcessingJob)

    def by_idempotency_key(self, key: str):
        return self.session.scalar(select(models.ProcessingJob).where(models.ProcessingJob.idempotency_key==key))

class ChangeResultRepository(Repository[models.ChangeResult]):
    def __init__(self,session: Session): super().__init__(session,models.ChangeResult)

class ImpactAssessmentRepository(Repository[models.ImpactAssessment]):
    def __init__(self,session: Session): super().__init__(session,models.ImpactAssessment)

    def add(self, payload: schemas.ImpactAssessmentCreate):
        values=payload.model_dump(exclude={'affected_area'},exclude_none=True)
        if payload.affected_area:
            values['affected_area']=postgis_multipolygon(payload.affected_area)
        obj=models.ImpactAssessment(**values)
        self.session.add(obj)
        self.session.flush()
        return obj
