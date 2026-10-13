# Implementation Roadmap

## Phase 0 — Contract
Canonical schemas, invariants, lifecycle, provider interfaces, privacy classification and migration rules.

## Phase 1 — Experience Core
Append-only experience store, trajectory reconstruction, idempotent ingestion, provenance and temporal queries.

## Phase 2 — Memory Core
Episodic, semantic, entity, procedural/observational memory; lifecycle; confidence/salience; source links.

## Phase 3 — Retrieval
PostgreSQL full-text, pgvector, metadata/entity filters, temporal filtering and deterministic score fusion.

## Phase 4 — Temporal Relations
Typed relations, contradiction, supersession, generalization, temporal validity and graph projection interface.

## Phase 5 — Consolidation
Trajectory analysis, RCA, reflection, abstraction, cross-trajectory generalization and proposal/validation gates.

## Phase 6 — Dreaming
Offline scheduled consolidation, hygiene, deduplication, stale-memory detection and archival.

## Phase 7 — PreCog
Behavior representation, trajectory-aware context, predictive retrieval, ranker adapter and BestNextAction integration.

## Phase 8 — Capability Evolution
Skill/code/policy candidates plus Manager/Healer/Judge validation loops.

## Phase 9 — Continual Learning
Dataset generation, offline evaluation, drift detection, champion/challenger, promotion and rollback.

## Phase 10 — Execution Feedback
Capture authoritative runtime outcomes as append-only, idempotent Experience events.

## Phase 11 — Outcome Evaluation
Evaluate observed behavior accuracy, successful-outcome rate, confidence calibration, evidence coverage and minimum sample size.

## Phase 12 — Outcome-Gated Promotion
Compare candidate and champion on the same Experience cohort; enforce quality gain and non-regression guardrails; preserve report-aware rollback.

## Phase 13 — Promotion Audit Trail
Record candidate/baseline identity, provenance, cohort, metrics, guardrail failures, decision and timestamp in an append-only audit sink.

## Phase 14 — Durable Promotion Audit
Persist audit records in PostgreSQL, enforce idempotent replay and reject row mutation/truncation through database triggers. Apply the migration separately and use least-privilege database roles.

## Phase 15 — Audit Integrity Verification
Hash-chain newly appended audit events, serialize concurrent appends, verify event content/links/head, and report legacy records that predate integrity hashing.

## Phase 16 — External Audit Checkpoints
Sign periodic chain checkpoints with Ed25519, store them outside the database, and reconcile the signed sequence/hash against the live audit chain to detect local rewrites.

Every phase exits with deterministic tests and an explicit evaluation artifact. No later phase may be required for correctness of an earlier phase. Promotion decisions never imply deployment or runtime authorization.
