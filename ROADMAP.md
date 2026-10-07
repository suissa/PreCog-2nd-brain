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
BehaviorID representation, trajectory-aware context, predictive retrieval, Jev/ranker adapter and BestNextAction integration.

## Phase 8 — Capability Evolution
Skill/code/policy candidates plus Manager/Healer/Judge validation loops.

## Phase 9 — Continual Learning
Dataset generation, offline evaluation, drift detection, champion/challenger, promotion and rollback.

Every phase exits with deterministic tests and an explicit evaluation artifact. No later phase may be required for correctness of an earlier phase.