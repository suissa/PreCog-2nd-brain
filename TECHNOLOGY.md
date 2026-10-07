# Technology Baseline

## Required baseline

TypeScript — primary implementation language.

PostgreSQL — canonical v1 operational store. Use relational columns for identity/lifecycle/time, JSONB for extensible payloads and transactions for atomic writes.

pgvector — initial semantic index inside PostgreSQL. Embeddings are indexes, never canonical truth.

PostgreSQL full-text search — initial lexical retrieval. A dedicated BM25 engine is optional only when measurement justifies it.

Filesystem + Markdown — human-readable projection and review surface.

Git — versioning and audit for human-readable projections.

## Optional later

Graphiti with Neo4j or FalkorDB as a temporal graph projection.

Reranker as a provider-neutral adapter.

Object storage for large raw artifacts.

NATS or another broker for asynchronous consolidation when required.

## Provider neutrality
Core interfaces must support OpenRouter, OpenAI-compatible endpoints, Ollama, Laya and future local/proprietary providers.

## Embedding metadata
Every embedding stores model identifier, dimensions, normalization/version, source object/version, generated_at and provider adapter. Model changes must allow coexistence or deterministic re-indexing.

## Retrieval pipeline
query -> lexical candidates + vector candidates + entity candidates + temporal candidates + relation candidates -> union -> deterministic filters -> score fusion -> optional reranker -> evidence package

## Why PostgreSQL first
PreCog needs durable identity, temporal truth, provenance, lifecycle, conflict representation and rebuildability in addition to semantic similarity. PostgreSQL provides a compact v1 substrate and pgvector supplies vector indexing without making a separate vector service canonical.

## Dependency gate
Every new dependency is evaluated for correctness, durability, provenance, temporal support, operational complexity, TypeScript integration, self-hosting, license, migration path and benchmark impact.