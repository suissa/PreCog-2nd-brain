-- Rollback for sql/002_canonical_constraints.sql.
-- Keep 001_initial.sql as the canonical base migration.

DROP INDEX IF EXISTS behavior_intent_idx;
DROP INDEX IF EXISTS behavior_status_idx;
DROP INDEX IF EXISTS knowledge_validity_idx;
DROP INDEX IF EXISTS trajectory_status_time_idx;

ALTER TABLE relation DROP CONSTRAINT IF EXISTS relation_provenance_required;
ALTER TABLE knowledge DROP CONSTRAINT IF EXISTS knowledge_provenance_required;
ALTER TABLE knowledge DROP CONSTRAINT IF EXISTS knowledge_version_positive;
ALTER TABLE memory DROP CONSTRAINT IF EXISTS memory_schema_version_positive;
ALTER TABLE trajectory DROP CONSTRAINT IF EXISTS trajectory_schema_version_positive;
ALTER TABLE experience DROP CONSTRAINT IF EXISTS experience_schema_version_positive;

DROP TABLE IF EXISTS behavior;
