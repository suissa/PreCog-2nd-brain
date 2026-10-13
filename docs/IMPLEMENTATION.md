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
| 7 PreCog | prediction.py, ranker.py, next_action.py, behavior prediction and BestNextAction | Implemented baseline |
| 8 Capability Evolution | capability.py, evolution.py, Manager/Healer/Judge gate | Implemented baseline |
| 9 Continual Learning | evaluation.py, continual.py, offline evaluation and champion/challenger rollback | Implemented baseline |
| 10 Execution Feedback | feedback.py, runtime outcome capture as append-only Experience | Implemented baseline |
| 11 Outcome Evaluation | outcome_evaluation.py, prediction accuracy, outcome rate, Brier score and evidence coverage | Implemented baseline |

## Source-of-truth boundary

Experience is append-only and authoritative. Memory, knowledge, relations, indexes, projections and model candidates are derived state and therefore rebuildable or replaceable.

## Retrieval-to-feedback loop

`Experience -> Memory -> Retrieval -> Prediction -> BestNextAction -> Runtime execution -> ExecutionResult -> Experience`

`ExecutionFeedbackRecorder` accepts an outcome reported by the authoritative runtime and persists it as a new Experience. An explicit runtime `event_id` provides a stable idempotency key; replaying the same event does not duplicate the Experience, and reusing the key with conflicting content is rejected. The event's Behavior, action, outcome, trajectory, timestamps and provenance remain queryable.

The recorder does not execute or authorize actions, and a prediction is never evidence that an action succeeded. Only the runtime's reported result is captured. If a runtime has no upstream trace or memory identifiers, the external event ID is retained as provenance.

## Outcome evaluation

`OutcomeEvaluator` compares a captured prediction with the later observed Behavior and runtime outcome. It reports behavior accuracy, successful-outcome rate, mean confidence, Brier score, evidence coverage and the IDs of the experiences evaluated. Minimum sample size and quality thresholds are configurable; an empty or underpowered sample cannot pass the default gate.

A passing report is evidence for a separate promotion decision, not an instruction to deploy. Evaluation does not mutate experiences, promote models, or authorize runtime actions. Prediction confidence is evaluated against whether the predicted Behavior matches the observed Behavior; outcome success is measured separately.

## Production boundary

The Python implementation is the executable reference and deterministic contract harness. PostgreSQL is the canonical v1 production substrate; sql/001_initial.sql defines the initial storage topology. Provider-specific model, embedding and reranking integrations remain adapters.

## Phase guarantees

Each phase has an explicit invariant surface. Later cognitive phases do not participate in correctness of earlier phases. Prediction never authorizes execution; capability evolution never bypasses validation; dreaming never mutates experience; retrieval never treats embeddings as canonical truth. Execution feedback records runtime outcomes without granting authority to prediction or action selection.

The normative specification remains PRE-CORD.md; the roadmap remains ROADMAP.md.
