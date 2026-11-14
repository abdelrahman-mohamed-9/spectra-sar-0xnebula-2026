"""T05 database-facing contracts. Accept only referenced real SAR products.

These models validate shape, not truth of imagery. STAC URLs, checksums and
geophysical assumptions require verification by the upstream data owners.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal, Annotated
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

Polarization = Literal['VV', 'VH', 'HH', 'HV', 'HHHH']
Orbit = Literal['ASCENDING', 'DESCENDING']

class StrictSchema(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class PolygonGeometry(StrictSchema):
    type: Literal['Polygon', 'MultiPolygon']
    coordinates: list[Any]

    @model_validator(mode='after')
    def validate_geometry(self):
        # Structural validation only: full topology is verified in PostGIS with ST_IsValid.
        polys = [self.coordinates] if self.type == 'Polygon' else self.coordinates
        if not polys: raise ValueError('at least one polygon is required')
        for polygon in polys:
            if not isinstance(polygon, list) or not polygon: raise ValueError('polygon rings required')
            for ring in polygon:
                if not isinstance(ring, list) or len(ring) < 4: raise ValueError('ring requires at least four positions')
                for position in ring:
                    if not isinstance(position, list) or len(position) < 2 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in position[:2]):
                        raise ValueError('coordinates must contain numeric lon/lat')
                    if not (-180 <= position[0] <= 180 and -90 <= position[1] <= 90):
                        raise ValueError('EPSG:4326 coordinate outside lon/lat bounds')
                if ring[0] != ring[-1]: raise ValueError('polygon ring must close')
        return self

class SarSceneCreate(StrictSchema):
    provider: str = Field(min_length=2,max_length=60)
    collection: str = Field(min_length=2,max_length=100)
    provider_item_id: str = Field(min_length=2,max_length=255)
    product_type: str = Field(min_length=2,max_length=60)
    acquisition_start: datetime
    acquisition_end: datetime | None = None
    orbit_direction: Orbit | None = None
    relative_orbit: int | None = Field(default=None, ge=1)
    polarizations: list[Polarization] = Field(min_length=1)
    incidence_angle_deg: float | None = Field(default=None,ge=0,le=90,allow_inf_nan=False)
    footprint: PolygonGeometry | None = None
    stac_item: dict[str, Any]

    @field_validator('acquisition_start','acquisition_end')
    @classmethod
    def timezone_required(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('acquisition timestamps must include timezone')
        return value

    @model_validator(mode='after')
    def validate_provenance(self):
        if 'HHHH' in self.polarizations and self.product_type.upper() != 'GCOV':
            raise ValueError('HHHH is a GCOV diagonal channel; cannot relabel it as Sentinel-1 RTC polarization')
        if self.acquisition_end and self.acquisition_end < self.acquisition_start:
            raise ValueError('acquisition_end before acquisition_start')
        if len(set(self.polarizations)) != len(self.polarizations):
            raise ValueError('duplicate polarization')
        item=self.stac_item
        if item.get('type') != 'Feature' or item.get('id') != self.provider_item_id:
            raise ValueError('STAC item type/id must match provider_item_id')
        if not isinstance(item.get('properties'),dict) or not isinstance(item.get('assets'),dict) or not item['assets']:
            raise ValueError('STAC properties and non-empty assets required')
        if not any(isinstance(v,dict) and isinstance(v.get('href'),str) and v['href'].startswith(('https://','s3://')) for v in item['assets'].values()):
            raise ValueError('STAC must link at least one https:// or s3:// asset')
        return self

class ArtifactCreate(StrictSchema):
    project_id: UUID
    scene_id: UUID | None = None
    kind: Literal['raw_sar','calibrated_sar','filtered_sar','change_mask','confidence_map','risk_map','report','other']
    storage_uri: str = Field(min_length=6,max_length=2048)
    media_type: str = Field(min_length=3,max_length=120)
    size_bytes: int | None = Field(default=None,ge=0)
    sha256: str | None = Field(default=None,pattern=r'^[a-fA-F0-9]{64}$')
    crs: str | None = Field(default=None,max_length=100)
    pixel_size_m: float | None = Field(default=None,gt=0,allow_inf_nan=False)
    metadata_json: dict[str,Any] = Field(default_factory=dict)

    @field_validator('storage_uri')
    @classmethod
    def supported_uri(cls,v):
        if not v.startswith(('s3://','https://')): raise ValueError('storage_uri must use s3:// or https://')
        return v

class ScenePairCreate(StrictSchema):
    project_id: UUID
    aoi_id: UUID
    before_scene_id: UUID
    after_scene_id: UUID
    validation_status: Literal['pending','pass','warning','reject'] = 'pending'
    validation_report: dict[str,Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def distinct(self):
        if self.before_scene_id == self.after_scene_id: raise ValueError('before and after must differ')
        if self.validation_status != 'pending' and not self.validation_report:
            raise ValueError('non-pending validation status requires a report')
        return self

class ProcessingJobCreate(StrictSchema):
    project_id: UUID
    scene_pair_id: UUID | None = None
    job_type: Literal['preprocess','denoise','change_detection','impact_assessment','other']
    idempotency_key: str | None = Field(default=None,min_length=8,max_length=180)
    input_parameters: dict[str,Any] = Field(default_factory=dict)

class ChangeResultCreate(StrictSchema):
    job_id: UUID
    scene_pair_id: UUID
    change_mask_artifact_id: UUID
    confidence_artifact_id: UUID | None = None
    changed_area_m2: float | None = Field(default=None,ge=0,allow_inf_nan=False)
    mean_confidence: float | None = Field(default=None,ge=0,le=1,allow_inf_nan=False)
    algorithm: str = Field(min_length=2,max_length=100)
    algorithm_version: str = Field(min_length=1,max_length=100)
    evaluation_metrics: dict[str,Any] = Field(default_factory=dict)

class ImpactAssessmentCreate(StrictSchema):
    change_result_id: UUID
    job_id: UUID | None = None
    assessment_type: str = Field(min_length=2,max_length=64)
    risk_level: Literal['low','medium','high','critical','unknown'] | None = None
    affected_area: PolygonGeometry | None = None
    risk_artifact_id: UUID | None = None
    population_estimate: int | None = Field(default=None,ge=0)
    findings: dict[str,Any] = Field(default_factory=dict)
    methods_and_sources: dict[str,Any] = Field(default_factory=dict)

class RecordRead(StrictSchema):
    model_config = ConfigDict(extra='ignore',from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime

class SarSceneRead(RecordRead):
    provider: str
    collection: str
    provider_item_id: str
    product_type: str
    acquisition_start: datetime
    orbit_direction: str | None
    polarizations: list[str]

class ArtifactRead(RecordRead):
    project_id: UUID
    scene_id: UUID | None
    kind: str
    storage_uri: str
    media_type: str

class ScenePairRead(RecordRead):
    project_id: UUID
    before_scene_id: UUID
    after_scene_id: UUID
    validation_status: str

class ProcessingJobRead(RecordRead):
    project_id: UUID
    job_type: str
    status: str

class ChangeResultRead(RecordRead):
    job_id: UUID
    scene_pair_id: UUID
    algorithm: str
    mean_confidence: float | None

class ImpactAssessmentRead(RecordRead):
    change_result_id: UUID
    assessment_type: str
    risk_level: str | None
