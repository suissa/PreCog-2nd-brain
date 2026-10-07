# Pre-CORD — PreCog-2nd-Brain Formal Technical Contract

Status: NORMATIVE / SPECIFICATION-FIRST

## 1. Purpose
PreCog defines a persistent cognitive substrate that transforms execution experience into retrievable memories and validated knowledge while preserving original evidence and temporal provenance.

## 2. Formal model
Let E be the immutable experience stream and T the set of trajectories.

M = f_memory(E, T, C, P)

K = f_consolidate(E, M, K_previous)

R(q, s, t) -> ranked evidence

Future prediction is downstream:
P(BehaviorID | q, s, R, T, H)

PreCog therefore does not define prediction as memory itself.

## 3. Architectural laws

L1 — Experience immutability: committed experience is append-only. Corrections are new records.

L2 — Provenance closure: every derived memory and knowledge object is traceable to source experiences or trajectories.

L3 — Temporal explicitness: distinguish valid time from recorded time.

L4 — Derived-state rebuildability: projections can be rebuilt from authoritative experience plus versioned derivation metadata.

L5 — Multi-representation: textual, structured, vector and relational representations may coexist; none alone is canonical truth.

L6 — Retrieval is evidence selection: retrieval ranks evidence for context rather than dumping a memory store into a prompt.

L7 — Contradiction preservation: conflicting claims remain representable with provenance and temporal validity.

L8 — Provider neutrality: core contracts do not depend on a model vendor or inference API.

L9 — Privacy boundary: PII and secrets require classification, redaction and retention policy.

L10 — Deterministic core: identity, provenance, lifecycle, filtering and authorization are deterministic; models assist extraction, consolidation, ranking and reflection.

## 4. Canonical entities

Experience: experience_id, trajectory_id, occurred_at, recorded_at, actor reference, event_type, payload, provenance, schema_version. Optional fields include intent_id, behavior_id, action, observation, tool call/result, state and outcome.

Trajectory: trajectory_id, ordered experience references, started_at, ended_at, status and schema_version.

Memory: memory_id, memory_type, content, source experience/trajectory IDs, timestamps, valid interval, confidence, salience, lifecycle state, derivation and schema version.

Memory types: episodic, semantic, entity, procedural, observational.

Relation: source_id, target_id, relation_type, confidence, valid interval and provenance.

Initial relation vocabulary: derived_from, caused_by, supports, contradicts, generalizes, specializes, supersedes, follows, related_to, applies_to, predicts.

Knowledge: knowledge_id, statement, scope, evidence IDs, confidence, status, version, temporal validity and derivation.

Behavior: behavior_id, intent, preconditions, context, actions, expected outcome, invariants, failure modes, evidence, confidence, status and version.

## 5. Lifecycle
captured -> candidate -> validated -> active -> dormant -> superseded -> archived

Transitions are auditable. Archival is not deletion. Destructive deletion exists only for explicit privacy/retention policy.

## 6. Retrieval contract
Initial retrieval MUST expose lexical/BM25, semantic/vector, entity/metadata, temporal, trajectory and optional relation signals independently.

Every result contains object identity, score components, provenance, temporal validity and lifecycle state.

Start with deterministic score fusion. Learned ranking is a later experiment.

## 7. Consolidation contract
Consolidation receives immutable experience plus current derived state and emits a proposal containing evidence, observations, RCA/explanation, generalization, candidate knowledge changes, contradictions, confidence, expected benefit and validation requirements.

No proposal becomes active knowledge without the configured validation gate.

## 8. Provider adapters
Model-dependent operations are adapters: extraction, summarization, reflection, RCA, embedding, reranking and prediction.

Candidate providers include OpenRouter, OpenAI-compatible endpoints, Ollama and Laya. They are implementation details, never canonical schema dependencies.

## 9. Verification invariants
- committed experience is never silently overwritten;
- every derived object has provenance;
- relations reference valid endpoints;
- invalid temporal intervals are rejected;
- archived objects are excluded from active retrieval by default;
- provider replacement does not change core schemas;
- duplicate ingestion is idempotent;
- derived projections are rebuildable;
- restricted data cannot enter unrestricted embeddings, logs or traces.

## 10. XP.2Flow
XP.2Flow is the higher-level declarative evolution mechanism. PreCog supplies stages such as experience -> trajectory -> retrieval -> consolidation -> knowledge. Later flows may consume knowledge for capability, behavior, evaluation and new experience.

## 11. Research boundary
Consolidated mechanisms: persistent external memory, episodic/semantic/procedural distinctions, reflection, hybrid retrieval, temporal graphs, append-only experience and human-readable versioning.

Original research boundary: unified provenance, BehaviorID-aware retrieval, Memory-to-Behavior Gain, PreCog prediction, XP.2Flow-driven memory evolution and integration with ITI and CodeManager/CodeHealer.