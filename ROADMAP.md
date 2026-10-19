# Implementation Roadmap

## Phase 0 — Contract
Canonical schemas, invariants, lifecycle, append-only event store, provenance and migration rules.

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
Compare candidate/champion on the same Experience cohort; enforce quality gain and non-regression guardrails; preserve report-aware rollback.

## Phase 13 — Promotion Audit Trail
Record candidate/baseline identity, provenance, cohort, metrics, guardrail failures, decision and timestamp in an append-only audit sink.

## Phase 14 — Durable Promotion Audit
Persist audit records in PostgreSQL, enforce idempotent replay and reject row mutation/truncation through database triggers. Apply the migration separately and use least-privilege database roles.

## Phase 15 — Audit Integrity Verification
Hash-chain newly appended audit events, serialize concurrent appends, verify event content/links/head, and report legacy records that predate integrity hashing. Export signed head checkpoints as local JSON files for tamper evidence within the configured host and filesystem trust boundaries.

## Phase 16 — Signed Checkpoints and Reconciliation
Sign verified audit-chain heads with Ed25519, export portable JSON checkpoints to the local filesystem, and reconcile current database history against a retained checkpoint file. Detect invalid signatures, rollback/truncation, rewritten history, and invalid local chains. This local design does not claim protection against an attacker who controls both the database and the host/filesystem.

## Phase 17 — Local Checkpoint Operations
Provide a one-shot job suitable for local cron/systemd, an atomic no-overwrite filesystem checkpoint store, trusted public-key lookup by key ID, pre/post chain verification, stderr alerts, and an optional append-only local JSONL incident journal. Reconciliation must fail closed for missing checkpoints, unknown keys, invalid signatures or divergent history. All checkpoint operations work without cloud accounts, object storage, hosted schedulers, webhooks, or other external services. Key rotation retains old public keys for historical checkpoint verification.

## Phase 18 — Checkpoint Freshness Monitoring
Allow periodic verification to enforce a configured maximum age for the latest signed checkpoint, reject future or timezone-naive timestamps, and alert on stale evidence. Retain immutable re-attestations of an unchanged audit head so scheduled checkpoint creation can refresh freshness without overwriting historical files.

## Phase 19 — Local Scheduled Audit Operations
Provide a user-level systemd installer with separate persistent timers for checkpoint creation and verification, private environment-file permissions, journal-based operational visibility, and safe handling of existing configuration. The installer must not enable lingering or modify host-wide policy implicitly.

## Phase 20 — Preflight and Safe Activation
Validate configuration, interpreter and repository paths, PostgreSQL connectivity, Ed25519 key-pair consistency and permissions, and writable local paths before enabling scheduled jobs. A newly created template must never activate timers automatically. Preflight must not expose secrets or claim to verify audit-history integrity.

Every phase exits with deterministic tests and an explicit evaluation artifact. No later phase may be required for correctness of an earlier phase. Promotion decisions never imply deployment or runtime authorization.
