-- SPECTRA-SAR / M6 / P1 T03 — PostgreSQL 16 schema, v0.1.0
-- Run only on an empty project DB or via scripts/migrate.py. Real acquisitions only.
BEGIN;
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sar_scenes (
  id UUID PRIMARY KEY, provider TEXT NOT NULL, provider_scene_id TEXT NOT NULL,
  mission TEXT NOT NULL, product_type TEXT NOT NULL,
  acquired_at TIMESTAMPTZ NOT NULL, orbit_direction TEXT NOT NULL
    CHECK (orbit_direction IN ('ASCENDING','DESCENDING')),
  relative_orbit INTEGER CHECK (relative_orbit > 0),
  polarizations TEXT[] NOT NULL CHECK (cardinality(polarizations) > 0),
  incidence_angle_degrees DOUBLE PRECISION CHECK (incidence_angle_degrees BETWEEN 0 AND 90),
  provider_record_url TEXT NOT NULL CHECK (provider_record_url ~ '^https://'),
  source_license TEXT NOT NULL, footprint_geojson JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(provider, provider_scene_id)
);
CREATE TABLE IF NOT EXISTS processing_runs (
  id UUID PRIMARY KEY, schema_version TEXT NOT NULL DEFAULT '0.1.0',
  status TEXT NOT NULL DEFAULT 'QUEUED'
    CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','REJECTED')),
  aoi_geojson JSONB, config JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
  error_code TEXT, error_message TEXT,
  CHECK (finished_at IS NULL OR finished_at >= created_at)
);
CREATE TABLE IF NOT EXISTS run_scene_pairs (
  run_id UUID PRIMARY KEY REFERENCES processing_runs(id) ON DELETE CASCADE,
  before_scene_id UUID NOT NULL REFERENCES sar_scenes(id) ON DELETE RESTRICT,
  after_scene_id UUID NOT NULL REFERENCES sar_scenes(id) ON DELETE RESTRICT,
  polarization TEXT NOT NULL CHECK (polarization IN ('VV','VH','HH','HV')),
  gatekeeper_status TEXT NOT NULL DEFAULT 'WARNING'
    CHECK (gatekeeper_status IN ('PASS','WARNING','REJECT')),
  gatekeeper_notes JSONB NOT NULL DEFAULT '[]'::jsonb,
  CHECK (before_scene_id <> after_scene_id)
);
CREATE TABLE IF NOT EXISTS stage_executions (
  id UUID PRIMARY KEY, run_id UUID NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
  component TEXT NOT NULL CHECK (component IN ('M1','M2','M3','M4','M5','M6')),
  stage_name TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt > 0),
  status TEXT NOT NULL CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','REJECTED')),
  producer_version TEXT, parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, error_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(run_id, component, stage_name, attempt)
);
CREATE TABLE IF NOT EXISTS artifacts (
  id UUID PRIMARY KEY, run_id UUID REFERENCES processing_runs(id) ON DELETE RESTRICT,
  scene_id UUID REFERENCES sar_scenes(id) ON DELETE RESTRICT,
  produced_by_stage_id UUID REFERENCES stage_executions(id) ON DELETE SET NULL,
  artifact_type TEXT NOT NULL,
  storage_uri TEXT NOT NULL CHECK (storage_uri ~ '^(s3|file)://'),
  sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  bytes_size BIGINT NOT NULL CHECK (bytes_size >= 0),
  mime_type TEXT, crs TEXT, raster_width INTEGER CHECK (raster_width > 0),
  raster_height INTEGER CHECK (raster_height > 0),
  backscatter_representation TEXT CHECK (backscatter_representation IN ('linear','dB')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (run_id IS NOT NULL OR scene_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS artifact_inputs (
  output_artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
  input_artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE RESTRICT,
  PRIMARY KEY(output_artifact_id, input_artifact_id),
  CHECK (output_artifact_id <> input_artifact_id)
);
CREATE TABLE IF NOT EXISTS analysis_results (
  id UUID PRIMARY KEY, run_id UUID NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
  result_kind TEXT NOT NULL CHECK (result_kind IN ('CHANGE','IMPACT','QUALITY')),
  method_name TEXT NOT NULL, method_version TEXT NOT NULL,
  change_asset_id UUID REFERENCES artifacts(id) ON DELETE RESTRICT,
  confidence_asset_id UUID REFERENCES artifacts(id) ON DELETE RESTRICT,
  confidence_interpretation TEXT NOT NULL DEFAULT 'not_provided'
    CHECK (confidence_interpretation IN ('calibrated_probability','uncalibrated_score','not_provided')),
  area_km2 DOUBLE PRECISION CHECK (area_km2 >= 0),
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (confidence_asset_id IS NOT NULL OR confidence_interpretation = 'not_provided')
);
CREATE TABLE IF NOT EXISTS audit_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id UUID REFERENCES processing_runs(id) ON DELETE SET NULL,
  actor_component TEXT NOT NULL, event_type TEXT NOT NULL,
  event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scenes_acquired ON sar_scenes(acquired_at);
CREATE INDEX IF NOT EXISTS idx_runs_status ON processing_runs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);
CREATE INDEX IF NOT EXISTS idx_stages_run ON stage_executions(run_id);
CREATE INDEX IF NOT EXISTS idx_results_run ON analysis_results(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_events(run_id, occurred_at DESC);
INSERT INTO schema_migrations(version) VALUES ('0.1.0') ON CONFLICT DO NOTHING;
COMMIT;
