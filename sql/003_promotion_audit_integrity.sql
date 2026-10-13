-- Phase 15: tamper-evident hash chain for newly appended promotion audit events.
-- Existing rows remain explicitly marked as legacy/unhashed; they are not retroactively
-- represented as cryptographically verified evidence.
CREATE SEQUENCE IF NOT EXISTS promotion_audit_sequence;
ALTER TABLE promotion_audit
    ADD COLUMN IF NOT EXISTS audit_sequence BIGINT,
    ADD COLUMN IF NOT EXISTS previous_hash TEXT,
    ADD COLUMN IF NOT EXISTS event_hash TEXT;

WITH numbered AS (
    SELECT event_id, row_number() OVER (ORDER BY recorded_at, event_id) AS seq
    FROM promotion_audit
    WHERE audit_sequence IS NULL
)
UPDATE promotion_audit AS audit
SET audit_sequence = numbered.seq
FROM numbered
WHERE audit.event_id = numbered.event_id;

SELECT setval(
    'promotion_audit_sequence',
    GREATEST(COALESCE((SELECT MAX(audit_sequence) FROM promotion_audit), 0), 1),
    COALESCE((SELECT MAX(audit_sequence) FROM promotion_audit), 0) > 0
);

ALTER TABLE promotion_audit
    ALTER COLUMN audit_sequence SET DEFAULT nextval('promotion_audit_sequence'),
    ALTER COLUMN audit_sequence SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS promotion_audit_sequence_idx
    ON promotion_audit (audit_sequence);

CREATE TABLE IF NOT EXISTS promotion_audit_chain_state (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    last_hash TEXT NOT NULL CHECK (length(last_hash) = 64)
);
INSERT INTO promotion_audit_chain_state (singleton, last_hash)
VALUES (TRUE, repeat('0', 64))
ON CONFLICT (singleton) DO NOTHING;

-- Migration backfill must be allowed to populate audit_sequence, but audit evidence
-- remains otherwise immutable. Reinstall append-only triggers after adding the columns.
