CREATE TABLE IF NOT EXISTS promotion_audit (
    event_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    candidate_version TEXT NOT NULL,
    candidate_provenance JSONB NOT NULL CHECK (jsonb_typeof(candidate_provenance) = 'array'),
    baseline_candidate_id TEXT,
    promoted BOOLEAN NOT NULL,
    reason TEXT NOT NULL,
    candidate_quality DOUBLE PRECISION NOT NULL CHECK (candidate_quality BETWEEN 0 AND 1),
    baseline_quality DOUBLE PRECISION CHECK (
        baseline_quality IS NULL OR baseline_quality BETWEEN 0 AND 1
    ),
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    evaluated_experience_ids JSONB NOT NULL CHECK (
        jsonb_typeof(evaluated_experience_ids) = 'array'
    ),
    behavior_accuracy DOUBLE PRECISION NOT NULL CHECK (behavior_accuracy BETWEEN 0 AND 1),
    successful_outcome_rate DOUBLE PRECISION NOT NULL CHECK (
        successful_outcome_rate BETWEEN 0 AND 1
    ),
    brier_score DOUBLE PRECISION NOT NULL CHECK (brier_score BETWEEN 0 AND 1),
    evidence_coverage DOUBLE PRECISION NOT NULL CHECK (evidence_coverage BETWEEN 0 AND 1),
    guardrail_failures JSONB NOT NULL CHECK (jsonb_typeof(guardrail_failures) = 'array'),
    recorded_at TIMESTAMPTZ NOT NULL,
    CHECK (NOT promoted OR jsonb_array_length(evaluated_experience_ids) > 0)
);

CREATE INDEX IF NOT EXISTS promotion_audit_candidate_time_idx
    ON promotion_audit (candidate_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS promotion_audit_recorded_at_idx
    ON promotion_audit (recorded_at, event_id);

CREATE OR REPLACE FUNCTION reject_promotion_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'promotion_audit is append-only: % is prohibited', TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS promotion_audit_no_row_mutation ON promotion_audit;
CREATE TRIGGER promotion_audit_no_row_mutation
    BEFORE UPDATE OR DELETE ON promotion_audit
    FOR EACH ROW EXECUTE FUNCTION reject_promotion_audit_mutation();

DROP TRIGGER IF EXISTS promotion_audit_no_truncate ON promotion_audit;
CREATE TRIGGER promotion_audit_no_truncate
    BEFORE TRUNCATE ON promotion_audit
    FOR EACH STATEMENT EXECUTE FUNCTION reject_promotion_audit_mutation();
