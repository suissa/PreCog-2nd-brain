# PreCog Implementation

| Phase | Executable implementation | Status |
|---|---|---|
| 0 Contract | models.py, contract.py, SQL constraints and privacy policy | Implemented |
| 1 Experience Core | store.py, trajectory.py, append-only idempotent ingestion and reconstruction | Implemented |
| 2 Memory Core | models.py, lifecycle, confidence/salience and provenance | Implemented |
| 3 Retrieval | retrieval.py, lexical/vector/temporal/relation deterministic fusion | Implemented |
| 4 Temporal Relations | relations.py, typed temporal relation graph projection | Implemented |
| 5 Consolidation | consolidation.py, proposal, contradiction detection and validation gate | Implemented |
| 6 Dreaming | dreaming.py, stale detection, deduplication and archival | Implemented |
| 7 PreCog | prediction.py, ranker.py, next_action.py, BehaviorID prediction and BestNextAction | Implemented baseline |
| 8 Capability Evolution | capability.py, evolution.py, Manager/Healer/Judge gate | Implemented baseline |
| 9 Continual Learning | evaluation.py, continual.py, offline evaluation and champion/challenger rollback | Implemented baseline |

## Source-of-truth boundary

Experience is append-only and authoritative. Memory, knowledge, relations, indexes, projections and model candidates are derived state and therefore rebuildable or replaceable.

## Production boundary

The Python implementation is the executable reference and deterministic contract harness. PostgreSQL is the canonical v1 production substrate; sql/001_initial.sql defines the initial storage topology. Provider-specific model, embedding and reranking integrations remain adapters.

## Phase guarantees

Each phase has an explicit invariant surface. Later cognitive phases do not participate in correctness of earlier phases. Prediction never authorizes execution; capability evolution never bypasses validation; dreaming never mutates experience; retrieval never treats embeddings as canonical truth.

The normative specification remains PRE-CORD.md; the roadmap remains ROADMAP.md.
