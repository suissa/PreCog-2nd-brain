# XP.2Flow — Declarative Experience Evolution Contract

Status: CONCEPT VALIDATION / NORMATIVE DESIGN CONTRACT  
Scope: protocol-level semantics and its integration boundary with PreCog-2nd-brain. This document does not claim that a general XP.2Flow runtime or YAML parser is implemented.

## 1. Responsibility split

- **XP.2Flow** declares a versioned, evaluable flow of semantic transformations. It is the protocol/orchestration layer.
- **PreCog** stores authoritative experience and provides cognitive capabilities: trajectory reconstruction, retrieval, consolidation proposals, knowledge validation, capability candidates, behavior prediction, and outcome capture.
- **A provider/model** may assist a declared step, but is never the authority for identity, provenance, policy, lifecycle transitions, or whether an outcome has been evidenced.

A flow definition is not itself experience or knowledge. It is a versioned declaration of how inputs may be transformed and what evidence is required for each transition.

## 2. Reference cognitive cycle

The canonical explanatory cycle is:

`Experience → Consolidation → Knowledge → Capability → Behavior → Experience`

This is a reference cycle, not a mandatory linear pipeline. Retrieval, trajectory reconstruction, evaluation, human review, privacy filtering, or domain-specific steps can be inserted, omitted, replaced, duplicated, or arranged in parallel when their contracts permit it. A flow may terminate at a proposal or evaluation result; it need not activate knowledge, create a capability, or execute a behavior.

The loop closes only when an actual observation or execution outcome is captured as a new Experience. A prediction or proposed action is not proof that the behavior occurred.

## 3. Flow model

A flow is a versioned directed graph, not an implicit ordered list. Each step has:

- `step_id`: stable identity within this flow version; repeated use of the same capability requires distinct step IDs.
- `kind`: semantic operation, such as `capture_experience`, `reconstruct_trajectory`, `retrieve_evidence`, `propose_consolidation`, `validate_knowledge`, `predict_behavior`, `propose_next_action`, or `evaluate_outcome`.
- `inputs` and `outputs`: named, typed values/references; outputs do not overwrite canonical Experience.
- `depends_on`: explicit data/control dependencies. Ordering is allowed only where required by data dependencies, declared effects, or semantic constraints.
- `preconditions` and `postconditions`: machine-checkable requirements for executing and accepting the step.
- `evidence_policy`: required provenance, validation gates, and contradiction handling.
- `version`: flow and step contract versions, kept with the execution record.
- `failure_policy`: fail, retry idempotently, defer for review, or take an explicitly declared alternative. A failed step must not silently fabricate output.

A concrete runtime schema may serialize these fields as YAML, JSON, or another representation. The serialization format is not the protocol's semantics.

## 4. Semantic validity and flexibility

Flexibility is constrained by contracts, not arbitrary reordering:

1. A step may move only if all declared dependencies remain satisfied and its effects commute with the steps it crosses.
2. Steps with non-commutative effects must have an explicit order.
3. Independent steps may run in parallel only when their input/output and effect contracts allow it.
4. A step may be removed only when no required output, invariant, evidence obligation, or downstream dependency relies on it.
5. Replacing a step requires a compatible contract or an explicit migration.
6. Duplicating a step requires a new step identity and explicit handling of idempotency and side effects.
7. Every step and flow version is evaluated independently; evaluation results must identify the exact versions and evidence cohort.
8. An unknown step kind, unresolved dependency, invalid type, or unsatisfied required precondition fails validation before execution.

Thus XP.2Flow is adaptable without becoming an unconstrained workflow engine.

## 5. PreCog invariants that a flow cannot override

- **Experience is append-only evidence.** Corrections and later observations are new records; a flow cannot rewrite prior Experience.
- **Provenance closure.** Every derived claim, memory, knowledge object, prediction, and evaluation result points to the source Experience/trajectory/evidence and derivation version.
- **Proposal is not activation.** Consolidation emits candidates. Configured validation/review gates must pass before knowledge or capability is promoted.
- **Contradictions remain visible.** A flow may resolve a decision for a bounded context, but cannot erase conflicting claims or their sources.
- **Temporal context is explicit.** Event time, recording time, and validity interval remain distinct.
- **Prediction is not execution.** `BestNextAction` is a proposal, not authorization. Runtime policy and authorization remain outside the predictive score.
- **Derived state is rebuildable.** Memory, indexes, summaries, and projections are reproducible from canonical evidence and versioned derivation metadata.
- **Privacy policy applies at every edge.** PII, secrets, and restricted fields cannot be made unrestricted by adding a step or changing providers.
- **Provider neutrality.** Replacing a model adapter must not alter canonical schemas or deterministic safety checks.
- **Idempotency and failure isolation.** Replaying a flow must not duplicate committed effects; provider/projection failures must not corrupt canonical experience.

## 6. Illustrative flow

The following is conceptual YAML, not a claim that a production XP.2Flow parser currently exists:

```yaml
xp2flow:
  id: precog.behavior-learning
  version: 1
  inputs:
    experience_id: ExperienceRef
  steps:
    - step_id: trajectory
      kind: reconstruct_trajectory
      inputs:
        experience: ${inputs.experience_id}
      outputs:
        trajectory: TrajectoryRef
      depends_on: []
      preconditions: [experience_exists]
      postconditions: [trajectory_has_provenance]
      failure_policy: fail

    - step_id: evidence
      kind: retrieve_evidence
      inputs:
        trajectory: ${steps.trajectory.trajectory}
      outputs:
        evidence: EvidenceSet
      depends_on: [trajectory]
      preconditions: [privacy_policy_applied]
      postconditions: [every_item_has_provenance]
      failure_policy: fail

    - step_id: consolidation
      kind: propose_consolidation
      inputs:
        evidence: ${steps.evidence.evidence}
      outputs:
        proposal: ConsolidationProposal
      depends_on: [evidence]
      preconditions: [evidence_non_empty]
      postconditions: [proposal_is_candidate_only]
      failure_policy: defer_for_review

    - step_id: outcome_eval
      kind: evaluate_outcome
      inputs:
        proposal: ${steps.consolidation.proposal}
      outputs:
        evaluation: EvaluationReport
      depends_on: [consolidation]
      preconditions: [evaluation_contract_available]
      postconditions: [report_contains_cohort_and_versions]
      failure_policy: fail
```

This example intentionally ends at evaluation. A separate declared transition can validate knowledge, propose a capability, predict a behavior, or select a next action when the required contracts and evidence exist. Only a later observed outcome creates the next Experience.

## 7. Mapping to the current PreCog code

The repository already contains components that can serve as step implementations:

| XP.2Flow semantic operation | Existing PreCog building block | Validation boundary |
|---|---|---|
| Capture / persist experience | `Experience`, `InMemoryStore.append_experience` | Append-only identity, idempotency, schema and provenance |
| Reconstruct trajectory | `precog.trajectory` | Missing/duplicate IDs and temporal ordering are explicit |
| Retrieve evidence | `HybridRetriever`, `RetrievalRepository` | Scores, provenance, time and lifecycle are retained |
| Propose consolidation | `Consolidator` / `ConsolidationEngine` | Proposal only; evidence and contradictions retained |
| Validate / materialize knowledge | Consolidation review and knowledge models | Validation gate; no implicit promotion |
| Propose capability | `CapabilityValidator` | Evidence, expected gain and risk threshold |
| Predict behavior | `BehaviorPredictor` | Evidence-backed prediction, not authorization |
| Select next action | `BestNextActionSelector` | Returns a proposal; does not execute it |
| Capture outcome / evaluate | Experience and evaluation modules | Actual outcome becomes a new immutable Experience |

These are building blocks, not proof of a complete XP.2Flow runtime. The repository now has an initial deterministic structural validator in `src/precog/xp2flow.py` with contract tests in `tests/test_xp2flow.py`. It checks unique step IDs, dependencies, cycles, optional registered step kinds, deterministic topological order, and undeclared read/write conflicts. It is deliberately not a general YAML schema, scheduler, or executor, and its effect analysis is only as complete as the effects declared by each step.

## 8. Minimum validation suite for an XP.2Flow runtime

Before calling a flow executable, tests must prove:

- valid dependency graph is accepted; cycles and unresolved dependencies are rejected;
- step ordering respects dependencies and declared effects;
- independent steps can be reordered without changing semantic outputs for a deterministic fixture;
- a forbidden reordering of non-commutative steps is rejected;
- add/remove/replace/duplicate operations validate against the contract and produce a new flow version;
- invalid input/output types and unsatisfied preconditions fail before effects occur;
- replay is idempotent and a failed adapter cannot mutate canonical Experience;
- every derived result has transitive provenance to original Experience;
- contradictory evidence is preserved and blocks automatic promotion when policy requires review;
- prediction/BestNextAction cannot bypass authorization or cause an unobserved outcome to be recorded as fact;
- a run report records flow/step versions, input identities, evidence IDs, decisions, failures, and actual outcomes;
- privacy classification is enforced across every step boundary.

The first validator milestone is implemented as a provider-free Python API; its tests cover graph validity, deterministic ordering, safe independence, dependency failures, and effect conflicts. The next milestone is a typed step-contract registry and execution records, followed by a controlled executor over registered Python adapters. Add YAML parsing only after the semantic contract and tests are stable.

## 9. Decision

XP.2Flow is a coherent fit for PreCog when treated as a **declarative, versioned semantic graph over evidence-preserving cognitive operations**. The structural validator is implemented, but XP.2Flow is not implemented end-to-end: typed step contracts, execution, versioned run records, provenance propagation through execution, and recovery behavior remain future work. Existing PreCog components can then be adapted as registered steps. The runtime must enforce PreCog invariants independently of LLM output.
