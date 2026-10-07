-- Phase 0/Memory lifecycle version metadata.
-- Forward migration after sql/002_canonical_constraints.sql.

ALTER TABLE memory
    ADD COLUMN version INTEGER NOT NULL DEFAULT 1
    CHECK (version >= 1);

CREATE INDEX IF NOT EXISTS memory_version_idx
    ON memory (memory_id, version);
