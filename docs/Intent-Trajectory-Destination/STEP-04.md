# STEP-04 — Schemas, Types, Validations, Tests, Constraints and Invariants

STEP-03 defines the semantic branches. STEP-04 turns those branches into an implementation contract: every scenario must have a representable type, a validation rule, a testable expectation, explicit constraints, and invariants that cannot be violated silently.

This document remains technology-agnostic. The schemas are logical schemas, not a database or language-specific schema.

## 1. Canonical result model

Every operation must return an explicit semantic result.

```
Result<T, E> =
  Valid<T>
  | Invalid<E>
```

Scenario execution must never encode semantic failure as an absent value, generic exception, boolean without meaning, or implicit control flow.

Core enums:

```
ConditionStatus = True | False | Unknown

TrajectoryStatus =
  Active
  | Reached
  | NotReached
  | Blocked
  | Invalidated
  | Undetermined

BranchClass =
  VALID_PROGRESS
  | VALID_NO_PROGRESS
  | VALID_RECOVERY
  | VALID_TERMINAL
  | INVALID_INPUT
  | INVALID_STATE
  | INVALID_TRANSITION
  | INVALID_EVIDENCE
  | INVALID_CONSTRAINT
  | INVALID_DESTINATION
  | INVALID_TERMINATION

TransitionStatus =
  Succeeded
  | PartiallySucceeded
  | Failed
  | Blocked
  | Undetermined

EvaluationDecision =
  Continue
  | Replan
  | Validate
  | Blocked
  | Invalidated
  | Undetermined
```

## 2. Common primitive schemas

```
Id {
  value: non-empty stable identifier
}

Provenance {
  sourceId
  sourceType
  recordedAt
  origin
}

TemporalPosition {
  validFrom?
  validUntil?
  recordedAt
}

Predicate {
  id
  expression
  scope
}

Condition {
  id
  predicate
  status: True | False | Unknown
  evidenceIds[]
}
```

Validation rules:

- IDs cannot be empty.
- Provenance is mandatory for derived facts.
- temporal intervals cannot have validUntil earlier than validFrom.
- predicates must be evaluable or explicitly marked unevaluable.
- Unknown must never be coerced to True.
- every True/False condition must have sufficient supporting evidence according to its contract.

## 3. Intent schema

```
Intent {
  id
  actor?
  expression
  requestedOutcome?
  entities[]
  explicitRequirements[]
  context?
  constraints[]
  preferences[]
  temporalConditions[]
  authorizationContext?
  uncertainty[]
  provenance
  createdAt
}
```

Validation:

```
expression != empty
id is stable
provenance exists
createdAt exists
```

Valid tests:

- minimal Intent with only expression;
- complete Intent;
- Intent with unresolved actor;
- Intent with unresolved outcome;
- Intent with contradiction;
- Intent with temporal condition.

Invalid tests:

- empty expression;
- missing identity;
- missing provenance;
- mutation after creation;
- invented outcome.

Invariant:

```
Intent_before == Intent_after
```

for the complete original representation.

## 4. UnderstoodIntent schema

```
UnderstoodIntent {
  sourceIntentId
  interpretation
  actor?
  desiredOutcome?
  entities[]
  explicitRequirements[]
  inferredRequirements[]
  ambiguities[]
  contradictions[]
  missingInformation[]
  temporalMeaning?
  uncertainty[]
  outcome:
    Understood
    | UnderstoodWithUncertainty
    | NeedsClarification
    | Contradictory
    | Unresolvable
}
```

Validation:

- source Intent must exist;
- inferred requirements cannot appear in explicit requirements;
- every ambiguity has an identifiable subject;
- every contradiction references conflicting claims;
- missing information must identify what is missing.

Tests:

- clear Intent -> Understood;
- ambiguous Intent -> NeedsClarification;
- contradictory Intent -> Contradictory;
- missing data -> explicit missingInformation;
- inference -> inferredRequirements.

Forbidden:

- silently resolving ambiguity;
- inventing missing data;
- executing Action;
- creating Goal;
- deleting contradiction.

Invariant:

```
sourceIntentId == Intent.id
```

## 5. NormalizedIntent schema

```
NormalizedIntent {
  sourceUnderstoodIntentId
  canonicalPurpose
  actor?
  entities[]
  requirements[]
  constraints[]
  preferences[]
  temporalConditions[]
  uncertainty[]
  unresolvedAmbiguities[]
}
```

Validation:

- source exists;
- all explicit requirements remain represented;
- inferred semantics retain their inferred status;
- ambiguities and contradictions are preserved;
- temporal semantics are preserved.

Tests:

- equivalent expressions normalize equivalently;
- normalization preserves requirements;
- normalization preserves uncertainty;
- normalization rejects semantic mutation.

Invariant:

```
semanticMeaning(before) == semanticMeaning(after)
```

## 6. ContextualizedIntent schema

```
ContextualizedIntent {
  normalizedIntentId
  relevantContext[]
  currentState?
  historicalFacts[]
  temporalContext?
  actorContext?
  environmentalContext?
  applicableRules[]
  priorExperience[]
  unresolvedContext[]
  outcome:
    Contextualized
    | ContextuallyIncomplete
    | ContextConflict
    | ContextStale
    | ContextInsufficient
}
```

Validation:

- context relevance is explicit;
- temporal validity is known;
- authoritative status is represented;
- historical context cannot masquerade as current context;
- conflicts remain visible.

Tests:

- no context;
- relevant context;
- irrelevant context;
- stale context;
- conflicting context;
- context affecting planning without changing Intent.

Invariant:

```
ContextualizedIntent does not mutate Intent or NormalizedIntent.
```

## 7. Goal schema

```
Goal {
  id
  sourceIntentId
  desiredOutcome
  successMeaning
  requiredSemanticChange[]
  traceability[]
}
```

Validation:

- desiredOutcome is semantic, not operational;
- successMeaning exists;
- source Intent is traceable;
- requiredSemanticChange is defined;
- no Action, Tool, Function, Endpoint, or implementation detail is used as the Goal itself.

Valid tests:

- outcome-oriented Goal;
- Goal with multiple required semantic changes;
- Goal traceability.

Invalid tests:

- Goal = tool call;
- Goal = API endpoint;
- Goal = workflow step;
- Goal introduces an unrelated objective;
- Goal removes an Intent requirement.

Invariants:

```
Goal.sourceIntentId == Intent.id
Goal != Action
Goal != Tool
```

## 8. Constraint schema

```
Constraint {
  id
  source
  predicate
  scope
  severity
  applicability
  violationMeaning
  active
}
```

Validation:

- predicate exists;
- source exists;
- scope exists;
- severity exists;
- violationMeaning exists;
- active constraints cannot be silently removed.

Tests:

- zero constraints;
- one constraint;
- multiple constraints;
- conditional constraint;
- conflicting constraints;
- constraint violation;
- attempted executor removal.

Invariants:

```
active Constraint remains active until explicit semantic revision
ConstraintViolation is observable
```

## 9. DestinationContract schema

```
DestinationContract {
  id
  goalId
  requiredOutcome
  requiredFinalState[]
  requiredEvidence[]
  constraints[]
  completionConditions[]
  failureConditions[]
  validationRules[]
}
```

Validation:

- goal exists;
- required outcome exists;
- final state is explicit;
- evidence requirements are explicit;
- completion conditions are evaluable;
- failure conditions are distinguishable;
- validation rules are deterministic or explicitly Unknown-capable.

Tests:

- valid semantic Destination;
- missing final state;
- missing evidence requirement;
- non-evaluable completion condition;
- Destination represented as Action;
- Destination changed after planning failure.

Invariant:

```
Destination defines completion, never implementation.
Destination cannot silently change during execution.
```

## 10. SemanticState schema

```
SemanticState {
  id
  predecessorStateId?
  facts[]
  conditions[]
  unresolvedConditions[]
  contradictions[]
  provenance[]
  temporalPosition
}
```

Validation:

- predecessor exists when state is derived;
- facts have provenance;
- conditions are explicit;
- contradictions are retained;
- temporal position is valid.

Tests:

- initial state;
- derived state;
- state with Unknown;
- state with contradiction;
- state with new Evidence;
- attempted historical overwrite.

Invariant:

```
State_n is derived from State_(n-1) + Transition + Evidence
```

## 11. CandidateTrajectory schema

```
CandidateTrajectory {
  id
  originStateId
  destinationId
  transitions[]
  dependencies[]
  alternatives[]
  validationPoints[]
  failurePoints[]
}
```

Validation:

- origin state exists;
- Destination exists;
- every Transition has objective;
- every Transition has preconditions;
- expected semantic changes exist;
- active Constraints are respected.

Tests:

- single-path plan;
- multi-path plan;
- alternative plan;
- blocked plan;
- impossible Transition;
- planner attempting to alter Goal;
- planner attempting to alter Destination.

Invariant:

```
Trajectory.destinationId == DestinationContract.id
```

## 12. Transition schema

```
Transition {
  id
  fromStateId
  objective
  preconditions[]
  requiredConstraints[]
  expectedChange[]
  completionConditions[]
  alternatives[]
}
```

Validation:

- objective is non-empty;
- source state exists;
- preconditions are evaluable;
- expected change exists;
- required Constraints are active;
- completion conditions are defined.

Tests:

- successful Transition;
- blocked precondition;
- violated Constraint;
- partial completion;
- failed Action;
- Unknown postcondition;
- no-op Transition.

Invariant:

```
Transition != Action
Transition has semantic objective
```

## 13. Action schema

```
Action {
  id
  transitionId
  actor
  operation
  authorization
  inputs[]
  result?
  status
}
```

Validation:

- Transition exists;
- actor is authorized;
- operation is defined;
- inputs satisfy operation requirements;
- result is mapped to Evidence when relevant.

Tests:

- authorized Action;
- unauthorized Action;
- unavailable Action;
- successful Action;
- failed Action;
- multiple Actions for one Transition.

Invalid:

- Action changes Goal;
- Action changes Destination;
- Action removes Constraint;
- Action declares global Destination success.

Invariant:

```
Action is subordinate to Transition.
```

## 14. Evidence schema

```
Evidence {
  id
  sourceTransitionId
  observedFact
  supports[]
  contradicts[]
  temporalPosition
  provenance
  confidence?
  quality?
}
```

Validation:

- source Transition exists;
- observedFact is explicit;
- provenance exists;
- temporal position exists;
- supports/contradicts references valid conditions.

Tests:

- supporting Evidence;
- contradicting Evidence;
- insufficient Evidence;
- conflicting Evidence;
- duplicate Evidence;
- missing provenance;
- fabricated expected-result Evidence.

Invariant:

```
Evidence is append-only.
Contradictory Evidence is preserved.
```

## 15. TransitionResult schema

```
TransitionResult {
  transitionId
  previousState
  resultingState
  evidence[]
  newlySatisfiedConditions[]
  unresolvedConditions[]
  contradictions[]
  constraintViolations[]
  status
}
```

Validation:

- Transition exists;
- previousState matches Transition.fromStateId;
- resultingState is derived from previousState;
- status agrees with conditions and Evidence;
- violations cannot be omitted.

Tests:

- succeeded;
- partially succeeded;
- failed;
- blocked;
- undetermined;
- contradictory result.

Invariant:

```
TransitionResult cannot declare DestinationReached.
```

## 16. TransitionEvaluation schema

```
TransitionEvaluation {
  transitionId
  decision
  reason[]
  stateAssessment
  evidenceAssessment
  constraintAssessment
  destinationAssessment
  nextStateId?
}
```

Validation precedence:

```
Invalidated
> Blocked
> Undetermined
> Validate
> Replan
> Continue
```

Tests:

- normal progress -> Continue;
- path failure -> Replan;
- impossible requirement -> Blocked;
- unresolved critical evidence -> Undetermined;
- possible completion -> Validate;
- Constraint violation -> Invalidated.

Invalid:

- Unknown -> Continue when critical;
- violation ignored;
- evaluation directly sets Reached;
- contradictory Evidence discarded.

## 17. DestinationValidation schema

```
DestinationValidation {
  destinationId
  requiredOutcomeSatisfied
  finalStateSatisfied
  requiredEvidenceSatisfied
  constraintsSatisfied
  completionConditionsSatisfied
  failureConditionsTriggered
  unresolvedContradictions[]
  evidence[]
  outcome
}
```

Validation:

```
Reached =
  requiredOutcomeSatisfied
  AND finalStateSatisfied
  AND requiredEvidenceSatisfied
  AND constraintsSatisfied
  AND completionConditionsSatisfied
  AND NOT failureConditionsTriggered
  AND no unresolved blocking contradiction
```

Tests:

- complete valid Destination -> Reached;
- incomplete state -> NotReached;
- insufficient Evidence -> Undetermined;
- impossible constraint -> Blocked;
- terminal contract violation -> Invalidated;
- Action success alone -> not Reached.

Invariant:

```
Only DestinationValidation can establish Reached.
```

## 18. TerminalOutcome schema

```
TerminalOutcome {
  trajectoryId
  destinationId
  status
  finalStateId
  evidenceIds[]
  satisfiedConditions[]
  unsatisfiedConditions[]
  constraintStatus
  reason[]
  provenance
}
```

Validation:

- trajectory and Destination exist;
- status matches DestinationValidation;
- final state is present;
- Evidence is traceable;
- reason is present.

Tests:

- each terminal status independently;
- generic Success rejected;
- generic Failure rejected;
- terminal result without Evidence rejected;
- terminal result inconsistent with validation rejected.

Invariant:

```
TerminalOutcome.status == DestinationValidation.outcome
```

## 19. Trajectory aggregate schema

```
Trajectory {
  id
  intentId
  goalId
  destinationId
  currentStateId
  planIds[]
  transitionIds[]
  evidenceIds[]
  status
  version
  provenance
}
```

Validation:

- Intent, Goal and Destination are traceable;
- current state exists;
- all referenced objects exist;
- status is consistent with latest validation;
- terminal trajectory cannot silently accept new Actions.

Invariant:

```
Intent -> Goal -> Destination -> Trajectory
```

is immutable as semantic identity.

## 20. Scenario test schema

Every STEP-03 scenario should be representable as:

```
Scenario {
  id
  category
  stage
  preconditions[]
  input
  branch
  expectedResult
  expectedEvidence[]
  expectedState
  expectedOutcome
  violatedInvariant?
}
```

Categories:

```
VALID_PROGRESS
VALID_NO_PROGRESS
VALID_RECOVERY
VALID_TERMINAL
INVALID_INPUT
INVALID_STATE
INVALID_TRANSITION
INVALID_EVIDENCE
INVALID_CONSTRAINT
INVALID_DESTINATION
INVALID_TERMINATION
```

A scenario is incomplete if it has no expected semantic result.

## 21. Mandatory test families

Every schema and operation must have:

### Construction tests

- minimal valid object;
- maximal valid object;
- optional fields absent;
- multiple related elements.

### Validation tests

- each required field missing;
- each invalid enum;
- invalid reference;
- invalid temporal interval;
- invalid predicate;
- invalid status combination.

### Invariant tests

- immutability;
- provenance;
- traceability;
- semantic identity;
- Unknown preservation;
- contradiction preservation.

### Scenario tests

- every valid scenario from STEP-03;
- every invalid scenario from STEP-03;
- every branch outcome.

### Mutation tests

Attempt:

- Intent mutation;
- Goal mutation;
- Constraint removal;
- Destination mutation;
- Evidence deletion;
- historical State overwrite;
- terminal trajectory mutation.

Every forbidden mutation must be rejected.

### Property tests

The implementation must preserve:

```
meaning(normalize(x)) == meaning(x)
```

and:

```
unknown(x) != true(x)
```

and:

```
actionSuccess(x) != destinationSuccess(x)
```

and:

```
planChange(x) != destinationChange(x)
```

unless an explicit semantic revision occurs.

## 22. Cross-stage scenario tests

### Clarification

Input:
```
UnderstoodIntent.missingInformation != empty
```

Expected:
```
NeedsClarification
```

Forbidden:
```
inventMissingInformation
```

### Contradiction

Input:
```
supportingEvidence != empty
contradictingEvidence != empty
```

Expected:
```
Contradiction preserved
```

Forbidden:
```
delete one side
```

### Partial progress

Input:
```
expectedChange is partially satisfied
```

Expected:
```
PartiallySucceeded
```

Forbidden:
```
Succeeded
```

### No-op

Input:
```
stateBefore == stateAfter
```

Valid only when:
- observation is the declared purpose; or
- useful new Evidence was produced.

Otherwise:
```
VALID_NO_PROGRESS
```

### Repeated transition

Valid only when:
- retry is explicitly allowed;
- retry is bounded; or
- state/Evidence/reason changes.

Otherwise invalid.

### Terminal protection

After Reached, Blocked, or Invalidated:

```
new Action -> INVALID_TERMINATION
```

unless an explicit new trajectory/recovery version is created.

## 23. Global invariants

I1. Original Intent is immutable.

I2. Every derived object has semantic provenance.

I3. Every Goal is traceable to Intent.

I4. Every Destination is traceable to Goal.

I5. Destination is defined before execution.

I6. Constraints remain active unless explicitly revised.

I7. Every Transition has a semantic objective.

I8. Actions cannot redefine semantic meaning.

I9. Evidence cannot be silently deleted.

I10. Contradictory Evidence remains represented.

I11. Unknown is never implicitly True or False.

I12. State transitions are reconstructable.

I13. Transition success does not imply Destination success.

I14. Only DestinationValidation establishes Reached.

I15. Replanning cannot silently change Intent, Goal, Constraints, or Destination.

I16. Terminal outcomes are explicit and distinguishable.

I17. Terminal history cannot be silently overwritten.

I18. A scenario branch must be observable and testable.

I19. Every invalid scenario has an explicit rejection or recovery path.

I20. No hidden semantic state may exist outside the trajectory model.

## 24. Global constraints

C1. No semantic operation may depend on implementation technology.

C2. No Action may be promoted to a Goal.

C3. No tool result may become truth without Evidence semantics.

C4. No missing information may be fabricated.

C5. No contradiction may be resolved by deletion.

C6. No failed plan may redefine its Destination.

C7. No validation may use implementation success as a substitute for semantic completion.

C8. No terminal result may exist without traceability.

C9. No retry loop may continue indefinitely without a declared boundary or semantic progress.

C10. No derived state may exist without an identifiable origin.

## 25. Minimum coverage matrix

The implementation must cover at least:

```
Intent                    valid + invalid + immutable
Understanding             clear + ambiguous + contradictory + missing
Normalization             equivalent + semantic-change rejection
Contextualization         relevant + absent + stale + conflicting
Goal                      outcome + implementation rejection
Constraint                none + single + multiple + conflict + violation
Destination               valid + incomplete + unevaluable + mutation rejection
SemanticState             initial + derived + unknown + contradiction
Planning                  valid + alternative + blocked + invalid
Transition                success + partial + failure + blocked + unknown
Action                    authorized + unauthorized + unavailable + failure
Evidence                  support + contradiction + insufficient + conflict
Evaluation                continue + replan + validate + blocked + invalidated + unknown
Replanning                alternative + preserved destination + loop prevention
DestinationValidation     all five terminal outcomes
TerminalOutcome           all statuses + consistency checks
Cross-stage               clarification + contradiction + partial + no-op + retry + terminal
```

Minimum rule:

```
Every STEP-03 branch
-> at least one positive test
-> at least one negative test when an invalid scenario exists
-> invariant assertion
```

## 26. Canonical scenario assertion

A complete scenario test must establish:

```
Given Input
When Branch executes
Then Result is expected
And Evidence is expected
And State is expected
And Outcome is expected
And no forbidden mutation occurred
And all applicable invariants hold
```

## 27. STEP-04 completion criterion

STEP-04 is complete when every object and every branch from STEP-03 has:

- a logical schema;
- typed states and outcomes;
- validation rules;
- valid scenario tests;
- invalid scenario tests;
- constraints;
- invariants;
- mutation/rejection tests;
- cross-stage tests;
- minimum coverage requirements.

The final implementation contract is:

```
Schema
 -> Type
 -> Validation
 -> Scenario
 -> Test
 -> Constraint
 -> Invariant
 -> Observable Result
```

No STEP-03 scenario is considered implemented if its semantic behavior exists only implicitly in control flow, exceptions, logs, or implementation-specific behavior.


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