# STEP-02 — Technical Semantic Execution Model

STEP-01 defined the semantic trajectory from Intent to Destination. STEP-02 defines the programmatic responsibility of each concept, its inputs and outputs, and the connections between them.

This document remains technology-agnostic. It defines semantic interfaces and execution contracts, not languages, databases, frameworks, transports, or model providers.

## 1. Technical pipeline

```
Intent
 -> understand
 -> UnderstoodIntent
 -> normalize
 -> NormalizedIntent
 -> contextualize
 -> ContextualizedIntent
 -> defineGoal
 -> Goal
 -> defineConstraints
 -> GoalWithConstraints
 -> defineDestination
 -> DestinationContract
 -> planTrajectory
 -> CandidateTrajectory
 -> executeTransition
 -> TransitionResult
 -> evaluateTransition
 -> Continue | Replan | Validate | Block | Invalidate | Undetermined
 -> validateDestination
 -> TerminalOutcome
```

The trajectory is a stateful semantic process, not merely a list of actions.

## 2. Core programmatic model

The implementation should have distinct concepts equivalent to:

```
Intent
UnderstoodIntent
NormalizedIntent
ContextualizedIntent
Goal
Constraint
DestinationContract
SemanticState
TrajectoryPlan
Transition
TransitionResult
Evidence
TransitionEvaluation
DestinationValidation
TerminalOutcome
Trajectory
```

They may be implemented as records, immutable values, objects, algebraic types, messages, or other structures. Their responsibilities must remain distinct.

## 3. Intent

Intent is the immutable origin.

```
Intent {
  id
  actor
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
}
```

The original Intent is never rewritten. Every later representation is derived from it.

```
UnderstoodIntent <- Intent
NormalizedIntent <- UnderstoodIntent
Goal <- ContextualizedIntent
DestinationContract <- Goal + Constraints
```

This creates semantic lineage.

## 4. Understanding

Contract:

```
understand(Intent) -> UnderstoodIntent
```

Responsibilities:

- identify actor and desired outcome;
- identify entities;
- separate explicit and inferred requirements;
- detect ambiguity;
- detect contradictions;
- identify missing information;
- preserve temporal meaning and uncertainty.

Conceptual output:

```
UnderstoodIntent {
  sourceIntentId
  interpretation
  actor
  desiredOutcome?
  entities[]
  explicitRequirements[]
  inferredRequirements[]
  ambiguities[]
  contradictions[]
  missingInformation[]
  temporalMeaning?
  uncertainty[]
}
```

It must not execute actions, invent facts, declare a Goal, or declare a Destination.

## 5. Normalization

Contract:

```
normalize(UnderstoodIntent) -> NormalizedIntent
```

Normalization produces a stable representation while preserving meaning.

Invariant:

```
meaning(NormalizedIntent) == meaning(UnderstoodIntent)
```

Conceptually:

```
NormalizedIntent {
  sourceUnderstoodIntentId
  canonicalPurpose
  actor
  entities[]
  requirements[]
  constraints[]
  preferences[]
  temporalConditions[]
  uncertainty[]
  unresolvedAmbiguities[]
}
```

Normalization changes representation, not intent.

## 6. Contextualization

Contract:

```
contextualize(NormalizedIntent, AvailableContext)
  -> ContextualizedIntent
```

The implementation must distinguish available context from relevant context.

```
RelevantContext = select(AvailableContext, IntentSemantics)
```

Conceptually:

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
}
```

Context enriches interpretation; it does not overwrite the original Intent.

## 7. Goal

Contract:

```
defineGoal(ContextualizedIntent) -> Goal
```

Goal answers:

```
What must ultimately become true?
```

Therefore:

```
Goal != Action
Goal != Function
Goal != ToolCall
Goal != WorkflowStep
```

Conceptually:

```
Goal {
  id
  sourceIntentId
  desiredOutcome
  successMeaning
  requiredSemanticChange
  traceability
}
```

The Goal becomes the semantic reference for planning and validation.

## 8. Constraints

Contract:

```
defineConstraints(ContextualizedIntent, Goal) -> Constraint[]
```

Conceptually:

```
Constraint {
  id
  source
  predicate
  scope
  severity
  applicability
  violationMeaning
}
```

A constraint is a condition that must remain true while pursuing the Goal.

Constraints remain active across transitions. Execution difficulty cannot silently remove one.

## 9. Destination Contract

Contract:

```
defineDestination(Goal, Constraints, ContextualizedIntent)
  -> DestinationContract
```

Conceptually:

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

The Destination Contract is defined before execution and must be independently evaluable.

Its predicate is conceptually:

```
validateDestination(
  DestinationContract,
  CurrentState,
  Evidence
) -> DestinationValidation
```

Execution cannot redefine success.

## 10. Semantic State

SemanticState represents what is currently believed to be true about the relevant domain.

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

A SemanticState is not simply application state. It is the state relevant to the Goal and Destination.

The current state must be reconstructable from its predecessor, transitions, and evidence.

## 11. Trajectory Plan

Contract:

```
planTrajectory(
  CurrentState,
  Goal,
  Constraints,
  DestinationContract
) -> CandidateTrajectory
```

Conceptually:

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

Each transition must state which semantic condition it attempts to make true.

A plan describes semantic changes, not merely technical calls.

Example:

```
Bad:
  call service X

Good:
  obtain authoritative confirmation that condition Y is true
```

The service call may implement the second statement, but is not the semantic transition itself.

## 12. Transition

A Transition is one meaningful state change.

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

Contract:

```
executeTransition(
  Transition,
  CurrentState,
  Constraints
) -> TransitionResult
```

Result:

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

A TransitionResult describes what happened locally. It does not declare the whole Destination reached.

## 13. Action is below Transition

This distinction is fundamental:

```
Transition
   -> Action(s)
   -> Observation
   -> Evidence
   -> Semantic State Change
```

Therefore:

```
Transition != Action
```

A technical Action is justified because it contributes to a semantic Transition.

```
Destination
  -> Transition Objective
  -> Required Action(s)
  -> Observed Result
  -> Evidence
  -> Semantic State
```

This prevents implementation details from defining the meaning of the trajectory.

## 14. Evidence

Evidence connects execution with semantic truth.

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
}
```

Evidence must answer:

- what was observed;
- when it was observed;
- where it came from;
- which condition it supports;
- which condition it contradicts.

Evidence is accumulated rather than silently overwritten.

If two observations conflict, the contradiction becomes part of the trajectory state.

## 15. Transition Evaluation

Contract:

```
evaluateTransition(
  TrajectoryState,
  TransitionResult,
  DestinationContract
) -> TransitionEvaluation
```

The evaluator checks:

1. Did the semantic state change?
2. Was the expected change achieved?
3. Is evidence sufficient?
4. Did a constraint become violated?
5. Did a contradiction appear?
6. Could the Destination now be satisfied?
7. Can the trajectory continue?
8. Must it replan?

Possible decisions:

```
Continue
Replan
Validate
Blocked
Invalidated
Undetermined
```

The evaluator decides the semantic next condition; it does not perform the next Action.

## 16. Replanning

Contract:

```
replan(CurrentState, DestinationContract, ExistingTrajectory)
  -> CandidateTrajectory
```

Replanning may change:

- path;
- intermediate states;
- transitions;
- actions;
- execution order.

It must preserve:

- Original Intent;
- Goal;
- Constraints;
- Destination;
- accumulated Evidence.

Thus:

```
Plan1 != Plan2
```

does not imply:

```
Destination1 != Destination2
```

Replanning changes the route, not the semantic destination.

## 17. Destination Validation

Contract:

```
validateDestination(
  DestinationContract,
  CurrentState,
  Evidence,
  Constraints
) -> DestinationValidation
```

Conceptually:

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

Only Destination Validation establishes the final Destination status.

Possible terminal outcomes:

```
Reached
NotReached
Blocked
Invalidated
Undetermined
```

Transition success is not Destination success.

## 18. Programmatic connection

```
Intent
  |
  v
Understanding
  |
  v
Normalization
  |
  v
Contextualization
  |
  v
Goal ------+
  |        |
  v        v
Constraints -> Destination
       |        |
       +---+----+
           |
           v
        Planning
           |
           v
       Transition
           |
           v
        Action(s)
           |
           v
        Evidence
           |
           v
     Semantic State
           |
           v
  Transition Evaluation
      |    |    |    |
      |    |    |    +-> Validate
      |    |    +------> Replan
      |    +-----------> Block / Invalidate
      +----------------> Continue
                           |
                           v
                   Destination Validation
                           |
                           v
                    Terminal Outcome
```

The architectural direction is:

```
Intent -> Meaning -> Destination -> Transition
       -> Evidence -> Validation
```

Actions exist below Transition.

## 19. Responsibility boundaries

| Concept | Responsibility |
|---|---|
| Intent | Preserve what was requested |
| Understanding | Determine meaning |
| Normalization | Produce stable equivalent meaning |
| Contextualization | Select relevant context |
| Goal | Define desired outcome |
| Constraint | Define what must remain true |
| Destination | Define completion |
| SemanticState | Represent current relevant truth |
| TrajectoryPlan | Define possible semantic paths |
| Transition | Define meaningful state change |
| Action | Perform implementation-level operation |
| Evidence | Support or contradict claims |
| TransitionEvaluation | Decide semantic continuation |
| Replanning | Generate another valid path |
| DestinationValidation | Determine Destination satisfaction |
| TerminalOutcome | Close the trajectory explicitly |

No component should absorb another component's responsibility merely for convenience.

## 20. Traceability

Every derived object must preserve its semantic origin.

```
Intent.id
  -> UnderstoodIntent.sourceIntentId
  -> NormalizedIntent.sourceUnderstoodIntentId
  -> ContextualizedIntent.sourceNormalizedIntentId
  -> Goal.sourceIntentId
  -> DestinationContract.goalId
  -> TrajectoryPlan.destinationId
  -> Transition.fromStateId
  -> Evidence.sourceTransitionId
  -> DestinationValidation.destinationId
```

The implementation must not require textual log inspection to discover why a derived object exists.

## 21. Semantic predicates

Conditions should be evaluable predicates:

```
Predicate(State, Evidence, Context)
  -> True | False | Unknown
```

Unknown is a first-class result:

```
Unknown != True
Unknown != False
```

An Unknown condition may require more evidence. It must not automatically become success or failure.

## 22. Preconditions and postconditions

Every Transition should define:

```
preconditions
expectedChange
postconditions
```

Execution establishes observations and Evidence.

Postconditions determine whether the local Transition succeeded.

Destination validation determines global completion.

Therefore:

```
Transition correctness != Destination correctness
```

Both are required.

## 23. Whole-trajectory invariants

1. Original Intent is immutable.
2. Every derived object has a traceable origin.
3. Goal changes require an explicit new or revised trajectory.
4. Destination cannot be silently changed during execution.
5. Constraints remain active until explicitly revised.
6. Every Transition has a semantic objective.
7. Every completed Transition produces a resulting state or explicit failure.
8. Evidence links observations to transitions and conditions.
9. Contradictions are preserved.
10. Unknown conditions remain Unknown until resolved.
11. Replanning cannot silently change Destination.
12. Actions are subordinate to Transitions.
13. Transition success does not imply Destination success.
14. Destination status is produced only by Destination Validation.
15. Terminal outcomes remain distinguishable.
16. The trajectory remains reconstructable from its semantic history.

## 24. Forbidden couplings

The following are invalid:

```
Intent -> Action
```

without Goal and Destination.

```
Action -> DestinationReached
```

without Evidence and Destination Validation.

```
ToolResult -> Goal
```

because a result is not an outcome definition.

```
Planner -> change Goal
```

because planning cannot redefine intent.

```
Executor -> remove Constraint
```

because execution difficulty cannot remove requirements.

```
Evidence -> overwrite Evidence
```

because conflicting history must remain available.

```
Unknown -> True
```

because lack of contradiction is not proof.

```
PlanFailure -> IntentFailure
```

because another valid trajectory may exist.

```
ActionSuccess -> DestinationSuccess
```

because technical execution and semantic completion are different predicates.

## 25. Minimal execution algorithm

```
intent = receiveIntent()

understood = understand(intent)
normalized = normalize(understood)
contextualized = contextualize(normalized)

goal = defineGoal(contextualized)
constraints = defineConstraints(contextualized, goal)

destination = defineDestination(
  goal,
  constraints,
  contextualized
)

state = initializeState(contextualized)

plan = planTrajectory(
  state,
  goal,
  constraints,
  destination
)

while not terminal:

  transition = selectNextTransition(plan, state)

  result = executeTransition(
    transition,
    state,
    constraints
  )

  evaluation = evaluateTransition(
    state,
    result,
    destination
  )

  state = result.resultingState

  if evaluation == Continue:
    plan = continue(plan, state)

  if evaluation == Replan:
    plan = replan(state, destination, trajectory)

  if evaluation == Validate:
    validation = validateDestination(
      destination,
      state,
      evidence,
      constraints
    )

  if evaluation == Blocked:
    terminal = Blocked

  if evaluation == Invalidated:
    terminal = Invalidated

  if evaluation == Undetermined:
    terminal = Undetermined

return terminal
```

The exact implementation may vary. The semantic order and responsibility boundaries may not.

## 26. Technical completion criterion

STEP-02 is complete when the implementation can programmatically answer:

1. What immutable Intent started the trajectory?
2. Which component interpreted it?
3. Which normalized representation resulted?
4. Which context was selected?
5. Which Goal was derived?
6. Which Constraints are active?
7. Which Destination Contract defines completion?
8. Which SemanticState is current?
9. Which Transition is being attempted?
10. Which Action(s) implement it?
11. Which Evidence resulted?
12. Which conditions became True, False, or Unknown?
13. Which constraints were preserved or violated?
14. Why did evaluation Continue, Replan, Block, Invalidate, or Validate?
15. What evidence proves or disproves the Destination?
16. Which TerminalOutcome was produced?
17. Can the entire semantic chain be reconstructed?

If these answers come from explicit programmatic relationships rather than inference from logs or implementation details, the Intent Trajectory has become technically implementable.

## 27. Fundamental technical principle

```
Intent       = origin
Goal         = desired outcome
Constraints  = boundaries
Destination  = completion definition
Trajectory   = semantic path
Transition   = meaningful state change
Action       = technical execution
Evidence     = justification of observed change
State        = current semantic truth
Evaluation   = decision about what happens next
Validation   = determination of Destination
Outcome      = explicit terminal result
```

Therefore:

```
Intent
 -> Goal
 -> Constraints
 -> Destination
 -> Trajectory
 -> Transition
 -> Action
 -> Evidence
 -> State
 -> Evaluation
 -> Validation
 -> Outcome
```

Technology may vary. These semantic responsibilities must not be collapsed into an undifferentiated execution pipeline.
