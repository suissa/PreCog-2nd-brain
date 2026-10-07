-- Rollback for sql/003_memory_version.sql.
DROP INDEX IF EXISTS memory_version_idx;
ALTER TABLE memory DROP COLUMN IF EXISTS version;
