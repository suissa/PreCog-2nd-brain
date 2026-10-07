-- Phase 1/P1 derived semantic retrieval projection.
-- Canonical memory remains the source of truth; vectors are rebuildable.

CREATE TABLE IF NOT EXISTS memory_embedding (
    memory_id TEXT PRIMARY KEY REFERENCES memory(memory_id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    provider_version TEXT NOT NULL,
    dimensions INTEGER NOT NULL CHECK (dimensions >= 1),
    source_version INTEGER NOT NULL CHECK (source_version >= 1),
    source_hash TEXT NOT NULL CHECK (length(source_hash) = 64),
    embedding vector NOT NULL
);

CREATE INDEX IF NOT EXISTS memory_embedding_model_idx
    ON memory_embedding (model, provider_version, dimensions);

CREATE INDEX IF NOT EXISTS memory_embedding_source_idx
    ON memory_embedding (memory_id, source_version);
