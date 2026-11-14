"""T03 schema for PostgreSQL 16 + PostGIS 3.4.

T03 defines models only. Do not call create_all in an API startup hook;
T04 owns migration/application of DDL and connection management.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, Index, Integer,
                        Float, String, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType


class Geometry(UserDefinedType):
    """PostGIS column DDL type; spatial serialization will be handled in T04."""
    cache_ok = True
    def __init__(self, shape: str, srid: int = 4326):
        self.shape, self.srid = shape, srid
    def get_col_spec(self, **kw):
        return f"geometry({self.shape},{self.srid})"


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Project(IdMixin, Timestamps, Base):
    __tablename__ = 'projects'
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    external_reference: Mapped[str | None] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'active'"))
    __table_args__ = (CheckConstraint("status IN ('active','archived')", name='ck_projects_status'),)


class AreaOfInterest(IdMixin, Timestamps, Base):
    __tablename__ = 'areas_of_interest'
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    geometry: Mapped[object] = mapped_column(Geometry('MULTIPOLYGON'), nullable=False)
    source_crs: Mapped[str | None] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint('project_id','label',name='uq_aoi_project_label'),)


class SarScene(IdMixin, Timestamps, Base):
    __tablename__ = 'sar_scenes'
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    collection: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    product_type: Mapped[str] = mapped_column(String(60), nullable=False)
    acquisition_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acquisition_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    orbit_direction: Mapped[str | None] = mapped_column(String(12))
    relative_orbit: Mapped[int | None] = mapped_column(Integer)
    polarizations: Mapped[list] = mapped_column(JSONB, nullable=False)
    incidence_angle_deg: Mapped[float | None] = mapped_column(Float)
    footprint: Mapped[object | None] = mapped_column(Geometry('MULTIPOLYGON'))
    stac_item: Mapped[dict] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        UniqueConstraint('provider','collection','provider_item_id',name='uq_scene_provider_item'),
        CheckConstraint("orbit_direction IS NULL OR orbit_direction IN ('ASCENDING','DESCENDING')",name='ck_scene_orbit_direction'),
        CheckConstraint('incidence_angle_deg IS NULL OR (incidence_angle_deg >= 0 AND incidence_angle_deg <= 90)',name='ck_scene_incidence'),
        CheckConstraint('acquisition_end IS NULL OR acquisition_end >= acquisition_start',name='ck_scene_acquisition_range'),
    )


class Artifact(IdMixin, Timestamps, Base):
    __tablename__ = 'artifacts'
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='RESTRICT'), nullable=False)
    scene_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('sar_scenes.id', ondelete='RESTRICT'))
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64))
    crs: Mapped[str | None] = mapped_column(String(100))
    pixel_size_m: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict] = mapped_column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    __table_args__ = (CheckConstraint('size_bytes IS NULL OR size_bytes >= 0',name='ck_artifact_size'),)


class ScenePair(IdMixin, Timestamps, Base):
    __tablename__ = 'scene_pairs'
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),nullable=False)
    aoi_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('areas_of_interest.id',ondelete='RESTRICT'),nullable=False)
    before_scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('sar_scenes.id',ondelete='RESTRICT'),nullable=False)
    after_scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('sar_scenes.id',ondelete='RESTRICT'),nullable=False)
    validation_status: Mapped[str] = mapped_column(String(16),nullable=False,server_default=text("'pending'"))
    validation_report: Mapped[dict] = mapped_column(JSONB,nullable=False,server_default=text("'{}'::jsonb"))
    __table_args__ = (
        UniqueConstraint('project_id','aoi_id','before_scene_id','after_scene_id',name='uq_scene_pair'),
        CheckConstraint('before_scene_id <> after_scene_id',name='ck_scene_pair_distinct'),
        CheckConstraint("validation_status IN ('pending','pass','warning','reject')",name='ck_scene_pair_validation'),
    )


class ProcessingJob(IdMixin, Timestamps, Base):
    __tablename__ = 'processing_jobs'
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id',ondelete='RESTRICT'),nullable=False)
    scene_pair_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('scene_pairs.id',ondelete='RESTRICT'))
    job_type: Mapped[str] = mapped_column(String(60),nullable=False)
    status: Mapped[str] = mapped_column(String(16),nullable=False,server_default=text("'queued'"))
    idempotency_key: Mapped[str | None] = mapped_column(String(180),unique=True)
    input_parameters: Mapped[dict] = mapped_column(JSONB,nullable=False,server_default=text("'{}'::jsonb"))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')",name='ck_job_status'),
        CheckConstraint('finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at',name='ck_job_times'),
    )


class ChangeResult(IdMixin, Timestamps, Base):
    __tablename__ = 'change_results'
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('processing_jobs.id',ondelete='RESTRICT'),nullable=False,unique=True)
    scene_pair_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('scene_pairs.id',ondelete='RESTRICT'),nullable=False)
    change_mask_artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('artifacts.id',ondelete='RESTRICT'),nullable=False)
    confidence_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('artifacts.id',ondelete='RESTRICT'))
    changed_area_m2: Mapped[float | None] = mapped_column(Float)
    mean_confidence: Mapped[float | None] = mapped_column(Float)
    algorithm: Mapped[str] = mapped_column(String(100),nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(100),nullable=False)
    evaluation_metrics: Mapped[dict] = mapped_column(JSONB,nullable=False,server_default=text("'{}'::jsonb"))
    __table_args__ = (
        CheckConstraint('changed_area_m2 IS NULL OR changed_area_m2 >= 0',name='ck_change_area'),
        CheckConstraint('mean_confidence IS NULL OR (mean_confidence >= 0 AND mean_confidence <= 1)',name='ck_change_confidence'),
    )


class ImpactAssessment(IdMixin, Timestamps, Base):
    __tablename__ = 'impact_assessments'
    change_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('change_results.id',ondelete='RESTRICT'),nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('processing_jobs.id',ondelete='RESTRICT'))
    assessment_type: Mapped[str] = mapped_column(String(64),nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(12))
    affected_area: Mapped[object | None] = mapped_column(Geometry('MULTIPOLYGON'))
    risk_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('artifacts.id',ondelete='RESTRICT'))
    population_estimate: Mapped[int | None] = mapped_column(Integer)
    findings: Mapped[dict] = mapped_column(JSONB,nullable=False,server_default=text("'{}'::jsonb"))
    methods_and_sources: Mapped[dict] = mapped_column(JSONB,nullable=False,server_default=text("'{}'::jsonb"))
    __table_args__ = (
        CheckConstraint("risk_level IS NULL OR risk_level IN ('low','medium','high','critical','unknown')",name='ck_impact_risk'),
        CheckConstraint('population_estimate IS NULL OR population_estimate >= 0',name='ck_impact_population'),
    )


class AuditEvent(IdMixin, Base):
    __tablename__ = 'audit_events'
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('projects.id',ondelete='SET NULL'))
    actor_id: Mapped[str] = mapped_column(String(180),nullable=False)
    action: Mapped[str] = mapped_column(String(120),nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80),nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_details: Mapped[dict] = mapped_column(JSONB,nullable=False,server_default=text("'{}'::jsonb"))


Index('ix_aoi_geom',AreaOfInterest.geometry,postgresql_using='gist')
Index('ix_scene_footprint',SarScene.footprint,postgresql_using='gist')
Index('ix_impact_geom',ImpactAssessment.affected_area,postgresql_using='gist')
Index('ix_sar_acquisition',SarScene.acquisition_start)
Index('ix_job_project_status',ProcessingJob.project_id,ProcessingJob.status)
Index('ix_pair_project',ScenePair.project_id)
Index('ix_artifact_project_kind',Artifact.project_id,Artifact.kind)
Index('ix_impact_change',ImpactAssessment.change_result_id)
Index('ix_audit_project_time',AuditEvent.project_id,AuditEvent.occurred_at)


# T10 identity and per-project authorization tables.
class User(IdMixin, Timestamps, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text('true'))
    is_platform_admin: Mapped[bool] = mapped_column(nullable=False, server_default=text('false'))

class ProjectMembership(Base):
    __tablename__ = 'project_memberships'
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    __table_args__ = (CheckConstraint("role IN ('viewer','analyst','editor','owner')", name='ck_membership_role'),)

Index('ix_membership_user', ProjectMembership.user_id)
