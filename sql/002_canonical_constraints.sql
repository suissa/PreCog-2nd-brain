-- Phase 0 canonical hardening.
-- Forward migration: psql ... -f sql/002_canonical_constraints.sql
-- Rollback: execute sql/002_canonical_constraints_down.sql

CREATE TABLE IF NOT EXISTS behavior (
    behavior_id TEXT PRIMARY KEY,
    intent TEXT NOT NULL,
    preconditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    context JSONB NOT NULL DEFAULT '[]'::jsonb,
    actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_outcome TEXT NOT NULL,
    evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1),
    status TEXT NOT NULL DEFAULT 'active',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version >= 1)
);

ALTER TABLE experience
    ADD CONSTRAINT experience_schema_version_positive
    CHECK (schema_version >= 1);

ALTER TABLE trajectory
    ADD CONSTRAINT trajectory_schema_version_positive
    CHECK (schema_version >= 1);

ALTER TABLE memory
    ADD CONSTRAINT memory_schema_version_positive
    CHECK (schema_version >= 1);

ALTER TABLE knowledge
    ADD CONSTRAINT knowledge_version_positive
    CHECK (version >= 1);

ALTER TABLE knowledge
    ADD CONSTRAINT knowledge_provenance_required
    CHECK (jsonb_typeof(provenance) = 'object');

ALTER TABLE relation
    ADD CONSTRAINT relation_provenance_required
    CHECK (jsonb_typeof(provenance) = 'object');

CREATE INDEX IF NOT EXISTS trajectory_status_time_idx
    ON trajectory (status, started_at);

CREATE INDEX IF NOT EXISTS knowledge_validity_idx
    ON knowledge (valid_from, valid_to);

CREATE INDEX IF NOT EXISTS behavior_status_idx
    ON behavior (status);

CREATE INDEX IF NOT EXISTS behavior_intent_idx
    ON behavior (intent);
