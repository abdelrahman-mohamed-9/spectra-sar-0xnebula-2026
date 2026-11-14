-- SPECTRA-SAR M5 T03 PostgreSQL 16 / PostGIS 3.4
-- Schema design reference; T04 will provide versioned migrations.
-- Requires CREATE privilege to install extension, typically performed by DB admin.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE projects (
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	external_reference VARCHAR(200), 
	status VARCHAR(24) DEFAULT 'active' NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_projects_status CHECK (status IN ('active','archived')), 
	UNIQUE (external_reference)
);

CREATE TABLE sar_scenes (
	provider VARCHAR(60) NOT NULL, 
	collection VARCHAR(100) NOT NULL, 
	provider_item_id VARCHAR(255) NOT NULL, 
	product_type VARCHAR(60) NOT NULL, 
	acquisition_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	acquisition_end TIMESTAMP WITH TIME ZONE, 
	orbit_direction VARCHAR(12), 
	relative_orbit INTEGER, 
	polarizations JSONB NOT NULL, 
	incidence_angle_deg FLOAT, 
	footprint geometry(MULTIPOLYGON,4326), 
	stac_item JSONB NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_scene_provider_item UNIQUE (provider, collection, provider_item_id), 
	CONSTRAINT ck_scene_orbit_direction CHECK (orbit_direction IS NULL OR orbit_direction IN ('ASCENDING','DESCENDING')), 
	CONSTRAINT ck_scene_incidence CHECK (incidence_angle_deg IS NULL OR (incidence_angle_deg >= 0 AND incidence_angle_deg <= 90)), 
	CONSTRAINT ck_scene_acquisition_range CHECK (acquisition_end IS NULL OR acquisition_end >= acquisition_start)
);

CREATE TABLE areas_of_interest (
	project_id UUID NOT NULL, 
	label VARCHAR(180) NOT NULL, 
	geometry geometry(MULTIPOLYGON,4326) NOT NULL, 
	source_crs VARCHAR(100), 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_aoi_project_label UNIQUE (project_id, label), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE artifacts (
	project_id UUID NOT NULL, 
	scene_id UUID, 
	kind VARCHAR(50) NOT NULL, 
	storage_uri TEXT NOT NULL, 
	media_type VARCHAR(120) NOT NULL, 
	size_bytes INTEGER, 
	sha256 VARCHAR(64), 
	crs VARCHAR(100), 
	pixel_size_m FLOAT, 
	metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_artifact_size CHECK (size_bytes IS NULL OR size_bytes >= 0), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT, 
	FOREIGN KEY(scene_id) REFERENCES sar_scenes (id) ON DELETE RESTRICT, 
	UNIQUE (storage_uri)
);

CREATE TABLE audit_events (
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	project_id UUID, 
	actor_id VARCHAR(180) NOT NULL, 
	action VARCHAR(120) NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id UUID, 
	event_details JSONB DEFAULT '{}'::jsonb NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL
);

CREATE TABLE scene_pairs (
	project_id UUID NOT NULL, 
	aoi_id UUID NOT NULL, 
	before_scene_id UUID NOT NULL, 
	after_scene_id UUID NOT NULL, 
	validation_status VARCHAR(16) DEFAULT 'pending' NOT NULL, 
	validation_report JSONB DEFAULT '{}'::jsonb NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_scene_pair UNIQUE (project_id, aoi_id, before_scene_id, after_scene_id), 
	CONSTRAINT ck_scene_pair_distinct CHECK (before_scene_id <> after_scene_id), 
	CONSTRAINT ck_scene_pair_validation CHECK (validation_status IN ('pending','pass','warning','reject')), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(aoi_id) REFERENCES areas_of_interest (id) ON DELETE RESTRICT, 
	FOREIGN KEY(before_scene_id) REFERENCES sar_scenes (id) ON DELETE RESTRICT, 
	FOREIGN KEY(after_scene_id) REFERENCES sar_scenes (id) ON DELETE RESTRICT
);

CREATE TABLE processing_jobs (
	project_id UUID NOT NULL, 
	scene_pair_id UUID, 
	job_type VARCHAR(60) NOT NULL, 
	status VARCHAR(16) DEFAULT 'queued' NOT NULL, 
	idempotency_key VARCHAR(180), 
	input_parameters JSONB DEFAULT '{}'::jsonb NOT NULL, 
	failure_reason TEXT, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_job_status CHECK (status IN ('queued','running','succeeded','failed','cancelled')), 
	CONSTRAINT ck_job_times CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT, 
	FOREIGN KEY(scene_pair_id) REFERENCES scene_pairs (id) ON DELETE RESTRICT, 
	UNIQUE (idempotency_key)
);

CREATE TABLE change_results (
	job_id UUID NOT NULL, 
	scene_pair_id UUID NOT NULL, 
	change_mask_artifact_id UUID NOT NULL, 
	confidence_artifact_id UUID, 
	changed_area_m2 FLOAT, 
	mean_confidence FLOAT, 
	algorithm VARCHAR(100) NOT NULL, 
	algorithm_version VARCHAR(100) NOT NULL, 
	evaluation_metrics JSONB DEFAULT '{}'::jsonb NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_change_area CHECK (changed_area_m2 IS NULL OR changed_area_m2 >= 0), 
	CONSTRAINT ck_change_confidence CHECK (mean_confidence IS NULL OR (mean_confidence >= 0 AND mean_confidence <= 1)), 
	UNIQUE (job_id), 
	FOREIGN KEY(job_id) REFERENCES processing_jobs (id) ON DELETE RESTRICT, 
	FOREIGN KEY(scene_pair_id) REFERENCES scene_pairs (id) ON DELETE RESTRICT, 
	FOREIGN KEY(change_mask_artifact_id) REFERENCES artifacts (id) ON DELETE RESTRICT, 
	FOREIGN KEY(confidence_artifact_id) REFERENCES artifacts (id) ON DELETE RESTRICT
);

CREATE TABLE impact_assessments (
	change_result_id UUID NOT NULL, 
	job_id UUID, 
	assessment_type VARCHAR(64) NOT NULL, 
	risk_level VARCHAR(12), 
	affected_area geometry(MULTIPOLYGON,4326), 
	risk_artifact_id UUID, 
	population_estimate INTEGER, 
	findings JSONB DEFAULT '{}'::jsonb NOT NULL, 
	methods_and_sources JSONB DEFAULT '{}'::jsonb NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_impact_risk CHECK (risk_level IS NULL OR risk_level IN ('low','medium','high','critical','unknown')), 
	CONSTRAINT ck_impact_population CHECK (population_estimate IS NULL OR population_estimate >= 0), 
	FOREIGN KEY(change_result_id) REFERENCES change_results (id) ON DELETE RESTRICT, 
	FOREIGN KEY(job_id) REFERENCES processing_jobs (id) ON DELETE RESTRICT, 
	FOREIGN KEY(risk_artifact_id) REFERENCES artifacts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_sar_acquisition ON sar_scenes (acquisition_start);
CREATE INDEX ix_scene_footprint ON sar_scenes USING gist (footprint);
CREATE INDEX ix_aoi_geom ON areas_of_interest USING gist (geometry);
CREATE INDEX ix_artifact_project_kind ON artifacts (project_id, kind);
CREATE INDEX ix_audit_project_time ON audit_events (project_id, occurred_at);
CREATE INDEX ix_pair_project ON scene_pairs (project_id);
CREATE INDEX ix_job_project_status ON processing_jobs (project_id, status);
CREATE INDEX ix_impact_change ON impact_assessments (change_result_id);
CREATE INDEX ix_impact_geom ON impact_assessments USING gist (affected_area);

-- Data integrity beyond simple check constraints, e.g. acquisition chronology,
-- cross-table project ownership and artifact/job provenance, must be enforced
-- in T04 application services and/or database triggers.
