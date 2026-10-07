CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS experience (
    experience_id TEXT PRIMARY KEY,
    trajectory_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    provenance JSONB NOT NULL,
    intent_id TEXT,
    behavior_id TEXT,
    action TEXT,
    outcome TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS experience_trajectory_time_idx
    ON experience (trajectory_id, occurred_at, experience_id);

CREATE TABLE IF NOT EXISTS trajectory (
    trajectory_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    experience_ids JSONB NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS memory (
    memory_id TEXT PRIMARY KEY,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source_ids JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    salience DOUBLE PRECISION NOT NULL CHECK (salience BETWEEN 0 AND 1),
    lifecycle TEXT NOT NULL,
    provenance JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector,
    schema_version INTEGER NOT NULL DEFAULT 1,
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE INDEX IF NOT EXISTS memory_lexical_idx ON memory USING GIN (to_tsvector('simple', content));
CREATE INDEX IF NOT EXISTS memory_lifecycle_idx ON memory (lifecycle);
CREATE INDEX IF NOT EXISTS memory_validity_idx ON memory (valid_from, valid_to);

CREATE TABLE IF NOT EXISTS knowledge (
    knowledge_id TEXT PRIMARY KEY,
    statement TEXT NOT NULL,
    scope TEXT NOT NULL,
    evidence_ids JSONB NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    provenance JSONB NOT NULL,
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS relation (
    relation_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    provenance JSONB NOT NULL,
    CHECK (source_id <> target_id),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE INDEX IF NOT EXISTS relation_source_idx ON relation(source_id);
CREATE INDEX IF NOT EXISTS relation_target_idx ON relation(target_id);
