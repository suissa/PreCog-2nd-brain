# STEP-01 — Intent Trajectory Destination

## 1. Objective

STEP-01 defines the macro execution model for transforming an incoming **Intent** into a validated **Destination** through explicit semantic states.

This document answers: **How does an Intent travel from what was initially expressed to the state in which its Destination can be proven to have been reached?**

It does not define technologies, frameworks, storage, model providers, protocols, or implementation languages. It defines the semantic transitions that any implementation must realize.

## 2. Macro Trajectory

```
INTENT
  ↓
[1] UNDERSTAND
  ↓
UNDERSTOOD INTENT
  ↓
[2] NORMALIZE
  ↓
NORMALIZED INTENT
  ↓
[3] CONTEXTUALIZE
  ↓
CONTEXTUALIZED INTENT
  ↓
[4] DEFINE GOAL
  ↓
GOAL
  ↓
[5] DEFINE CONSTRAINTS
  ↓
GOAL + CONSTRAINTS
  ↓
[6] DEFINE DESTINATION
  ↓
DESTINATION CONTRACT
  ↓
[7] PLAN TRAJECTORY
  ↓
CANDIDATE TRAJECTORY
  ↓
[8] EXECUTE SEMANTIC TRANSITIONS
  │
  ├────► EVIDENCE → STATE UPDATE → next transition
  ↓
[9] VALIDATE DESTINATION
  ↓
Reached | Not Reached | Blocked | Invalidated | Undetermined
```

Every stage consumes a semantic state and produces a more qualified semantic state.

## 3. State Model

```
S0 = Intent
S1 = UnderstoodIntent
S2 = NormalizedIntent
S3 = ContextualizedIntent
S4 = Goal
S5 = GoalWithConstraints
S6 = DestinationContract
S7 = CandidateTrajectory
S8 = TransitionState*
S9 = DestinationValidation
S10 = DestinationReached
```

TransitionState* is a variable sequence:

```
S7 → T1 → S8₁ → T2 → S8₂ → ... → Tn → S8ₙ
```

The number of transitions is not predetermined. The trajectory terminates when the Destination Contract can be evaluated conclusively.

## 4. Stage 1 — Understand Intent

**Input:** raw Intent as expressed by the actor.

Determine actor, desired outcome, referenced entities, explicit requirements, implied requirements, ambiguity, uncertainty, contradictions, and relevant temporal meaning.

**Output:** UnderstoodIntent.

The trajectory may leave this stage only when it can describe what the actor is attempting to accomplish, or explicitly declare that understanding is insufficient. If the Intent cannot be sufficiently understood, no downstream Goal or Destination may be invented.

## 5. Stage 2 — Normalize Intent

Convert different expressions of the same meaning into a stable semantic representation.

Normalization must preserve intent meaning, actor, relevant entities, requirements, uncertainty, and unresolved ambiguity. It may remove linguistic variation, but never semantic information.

**Output:** NormalizedIntent.

The normalized representation must be semantically equivalent to the understood Intent.

## 6. Stage 3 — Contextualize Intent

Determine which contextual information changes the interpretation or satisfaction of the Intent.

Relevant context can include current and previous state, previous interactions, historical facts, temporal conditions, actor context, environmental conditions, known relationships, and previous experiences.

The objective is not to collect all available context. It is to identify the minimum relevant context required to interpret and pursue the Intent correctly.

**Output:** ContextualizedIntent.

## 7. Stage 4 — Define Goal

Derive the desired outcome independently from the wording of the request.

The Goal answers: **What must ultimately become true?**

The Goal must be outcome-oriented rather than action-oriented. For example, 'send message' is an action; 'the intended recipient has received the required information' is an outcome.

**Output:** Goal.

The Goal must remain traceable to the original Intent.

## 8. Stage 5 — Define Constraints

Determine the conditions that must remain true while pursuing the Goal.

Constraints may include invariants, permissions, temporal boundaries, required preconditions, prohibited outcomes, actor responsibilities, dependencies, safety conditions, and resource or scope boundaries.

**Output:** GoalWithConstraints.

Every constraint must be attributable to the Intent, its context, or an explicitly applicable rule. Constraints cannot silently disappear.

## 9. Stage 6 — Define Destination

Construct the semantic definition of completion.

```
Destination =
    Required Outcome
  + Required Final State
  + Required Evidence
  + Constraints
  + Completion Conditions
  + Failure Conditions
```

The Destination is defined **before trajectory execution**. This prevents execution from redefining success according to whatever happened.

The Destination Contract must be explicit enough that an independent evaluator could determine whether it has been reached.

## 10. Stage 7 — Plan Trajectory

Given the Destination Contract and current contextual state, determine possible semantic transitions toward the Destination.

A transition is conceptually:

```
CurrentState + RequiredChange + TransitionConditions → NextState
```

Planning identifies intermediate states, dependencies, required information, decisions, prerequisites, alternative paths, failure points, and validation points.

The plan is a candidate, not a guarantee. A Destination may have multiple valid trajectories.

## 11. Stage 8 — Execute Semantic Transitions

This is the core of the trajectory.

Each transition receives the current semantic state, its transition objective, and applicable constraints, and attempts to produce a next semantic state plus evidence.

```
Tᵢ : (Sᵢ, C, Oᵢ) → (Sᵢ₊₁, Eᵢ)
```

Where Sᵢ is the current state, C the constraints, Oᵢ the transition objective, Sᵢ₊₁ the resulting state, and Eᵢ the evidence produced.

A transition is not successful merely because an action occurred. It is successful only when the resulting semantic state satisfies the expected transition conditions and evidence supports that claim.

## 12. Transition Evaluation

After every meaningful transition, evaluate:

- **State change:** what became different?
- **Progress:** did the change move toward the Destination?
- **Evidence:** what demonstrates that the change occurred?
- **Constraints:** did any constraint become violated?
- **Contradiction:** does new evidence contradict previous knowledge?
- **Continuation:** can the trajectory continue?
- **Replanning:** does the new state require another valid path?

Thus:

```
State → Transition → Evidence → Evaluate → Continue / Replan / Block / Invalidate → Next State
```

## 13. Evidence as the Connector

Evidence connects transitions to Destination validation.

Without evidence, 'the transition occurred' is only an assertion. Evidence provides the semantic justification for the resulting state.

Evidence remains associated with the transition that produced it, the state it supports, the conditions it confirms or rejects, relevant contradictions, and its temporal position in the trajectory.

The trajectory accumulates evidence rather than replacing previous evidence.

## 14. Replanning

A trajectory is not necessarily linear.

```
Planned State
     ↓
Actual State
     ↓
Evaluate
     ↓
Can Destination still be reached?
     ├── yes → replan
     ├── no  → invalidate/block
     └── unknown → obtain more evidence
```

Replanning changes the path. It must not silently change the original Intent, Goal, established constraints, or meaning of the Destination.

If the Goal itself must change, that is a new or explicitly revised Intent trajectory, not an invisible modification of the existing one.

## 15. Destination Validation

When the current semantic state appears capable of satisfying the Destination, evaluate the complete Destination Contract against current state, evidence, and constraints.

Validation asks:

1. Does the required outcome exist?
2. Does the required final state exist?
3. Are all completion conditions satisfied?
4. Are all constraints still satisfied?
5. Is sufficient evidence available?
6. Do unresolved contradictions prevent confirmation?

Only then can the trajectory become DestinationReached.

## 16. Terminal States

- **Reached:** Destination Contract is satisfied and supported by sufficient evidence.
- **Not Reached:** current state is valid but does not satisfy the Destination.
- **Blocked:** a required condition cannot currently be satisfied.
- **Invalidated:** a condition was violated and the current path is no longer valid.
- **Undetermined:** evidence is insufficient to establish whether the Destination has been reached.

These states must not collapse into a generic success/failure result.

## 17. Macro Data Flow

```
Intent
  │
  ├── meaning / actor / entities / uncertainty
  ▼
UnderstoodIntent
  ▼
NormalizedIntent
  │
  ├── relevant context
  ▼
ContextualizedIntent
  │
  ├── desired outcome
  ▼
Goal
  │
  ├── boundaries
  ▼
Goal + Constraints
  │
  ├── completion semantics
  ▼
DestinationContract
  │
  ├── possible transitions
  ▼
CandidateTrajectory
  │
  ├── transition → observation → evidence → evaluation
  └────────────── loop ───────────────┐
                                      ▼
                              Destination Validation
                                      │
                                      ▼
                                Terminal Outcome
```

## 18. Semantic Traceability

Information must remain traceable from beginning to end:

```
Original Intent → Interpretation → Context → Goal → Constraints → Destination → Trajectory → Transitions → Evidence → Final Validation
```

This creates a chain of semantic justification:

```
Why this Goal?        → Because of this Intent.
Why these Constraints? → Because of Intent + Context.
Why this Destination? → Because of Goal + Constraints.
Why this Transition?  → Because it advances toward the Destination.
Why this State?       → Because of Transition + Evidence.
Why Destination Reached? → Because the Destination Contract is satisfied by evidence.
```

## 19. Implementation Boundary

STEP-01 intentionally does not define implementation language, storage, database, message transport, API, model provider, agent framework, embedding, vector search, graph implementation, workflow engine, scheduling, or user interface.

It defines the semantic contract that any implementation must satisfy.

## 20. STEP-01 Completion Criterion

For any trajectory, an implementation must be able to answer:

1. What was the original Intent?
2. What did the system understand?
3. How was the Intent normalized?
4. What context affected its interpretation?
5. What Goal was derived?
6. Which Constraints apply?
7. What Destination was defined?
8. Which trajectory was selected?
9. Which semantic transitions occurred?
10. What evidence supports each transition?
11. Did the trajectory replan?
12. Were any constraints violated?
13. Why was the Destination considered reached or not reached?

If these questions cannot be answered, the trajectory is not semantically complete.

## 21. Fundamental Principle

```
An Intent does not travel directly to an Action.

An Intent travels through semantic states
until its Destination becomes demonstrably true.
```

Therefore:

```
Intent → Meaning → Context → Goal → Constraints → Destination → Trajectory → Transitions → Evidence → Validation → Destination
```

The trajectory is the chain connecting **what was intended** to **what became true**.

## Implementation Issues

The implementation is Python-first. The following issues are the executable work plan for completing this step and its dependencies.

- [#18 — Implement Intent Trajectory Python domain contracts (STEP-04)](https://github.com/suissa/PreCog-2nd-brain/issues/18)
- [#19 — Implement Intent Trajectory semantic pipeline (STEP-01/02)](https://github.com/suissa/PreCog-2nd-brain/issues/19)
- [#20 — Implement STEP-03 branch validators and scenario engine](https://github.com/suissa/PreCog-2nd-brain/issues/20)
- [#21 — Implement semantic execution, Evidence and State reconstruction](https://github.com/suissa/PreCog-2nd-brain/issues/21)
- [#22 — Implement deterministic TransitionEvaluation and Replanning](https://github.com/suissa/PreCog-2nd-brain/issues/22)
- [#23 — Implement DestinationValidation and terminal protection](https://github.com/suissa/PreCog-2nd-brain/issues/23)
- [#24 — Build complete Intent Trajectory scenario test suite](https://github.com/suissa/PreCog-2nd-brain/issues/24)
- [#25 — Add Python quality gate and traceability coverage for Intent Trajectory](https://github.com/suissa/PreCog-2nd-brain/issues/25)

Completion rule: the step is not complete until its applicable issues are implemented, tested, and the STEP-04 minimum coverage matrix is satisfied.