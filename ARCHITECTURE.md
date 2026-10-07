# PreCog Architecture

## System boundary
XP.2Flow is the declarative orchestration layer. PreCog is the persistent cognitive substrate.

experience -> memory -> retrieval -> consolidation -> knowledge -> downstream behavior

## Source-of-truth hierarchy
1. Immutable Experience is authoritative evidence.
2. Memory is reconstructable derived state.
3. Knowledge is validated abstraction.
4. Behavior is downstream normative/predictive projection.
5. Capability is executable realization.

## Storage topology
PostgreSQL: canonical relational state, JSONB payloads, temporal metadata and pgvector.
Filesystem/Markdown: human-readable derived projection.
Git: versioning/audit for projections.
Optional graph: Graphiti/Neo4j/FalkorDB projection after measured need.

## Core modules
- experience: append, validate, idempotency, trajectories, provenance
- memory: types, lifecycle, salience, confidence, source links
- retrieval: lexical, vector, metadata, temporal, relation-aware
- consolidation: RCA, reflection, abstraction, generalization, contradiction proposals
- knowledge: claims, patterns, evidence, validation, supersession
- provider: model, embedding and reranking adapters
- projection: Markdown/JSON/graph
- evaluation: retrieval, temporal, provenance and behavioral utility

## Retrieval pipeline
query + state + time -> candidate generation -> authorization/filtering -> score fusion -> optional reranking -> evidence package

## Failure isolation
Embedding, LLM, reranker, projection or graph failures MUST NOT corrupt canonical experience. Derived indexes and projections are rebuildable.

## Future cognitive layer
context + trajectory + retrieved evidence -> BehaviorID/Jev -> P(BehaviorID|context) -> BestNextAction -> new experience