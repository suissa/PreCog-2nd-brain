from __future__ import annotations
from dataclasses import replace
from .domain import (
    Constraint, ContextualizedIntent, DestinationContract, DestinationValidation, Evidence,
    EvaluationDecision, Goal, Intent, NormalizedIntent, TerminalStatus,
    TransitionEvaluation, UnderstoodIntent,
)

def understand(intent: Intent) -> UnderstoodIntent:
    missing = []
    ambiguities = []
    if not intent.expression.strip():
        missing.append("expression")
    outcome = intent.requested_outcome
    if not outcome:
        ambiguities.append("requested_outcome")
    if missing:
        return UnderstoodIntent(intent.id, intent.expression or "unresolved", "Unresolvable",
                                desired_outcome=outcome, ambiguities=tuple(ambiguities),
                                missing_information=tuple(missing))
    if ambiguities:
        return UnderstoodIntent(intent.id, intent.expression, "NeedsClarification",
                                desired_outcome=outcome, ambiguities=tuple(ambiguities))
    return UnderstoodIntent(intent.id, intent.expression, "Understood",
                            desired_outcome=outcome, explicit_requirements=intent.explicit_requirements)

def normalize(understood: UnderstoodIntent) -> NormalizedIntent:
    return NormalizedIntent(
        source_understood_intent_id=understood.source_intent_id,
        canonical_purpose=understood.desired_outcome or understood.interpretation,
        requirements=understood.explicit_requirements + understood.inferred_requirements,
        constraints=(),
        actor=understood.actor, entities=understood.entities,
        unresolved_ambiguities=understood.ambiguities,
        uncertainty=understood.uncertainty,
    )

def contextualize(normalized: NormalizedIntent, context: tuple[str, ...] = ()) -> ContextualizedIntent:
    outcome = "Contextualized" if not normalized.unresolved_ambiguities else "ContextuallyIncomplete"
    return ContextualizedIntent(normalized.source_understood_intent_id,
                                tuple(context), outcome, unresolved_context=normalized.unresolved_ambiguities)

def define_goal(contextualized: ContextualizedIntent, intent: Intent) -> Goal:
    if contextualized.outcome != "Contextualized":
        raise ValueError("cannot define Goal from incomplete context")
    desired = intent.requested_outcome or contextualized.normalized_intent_id
    return Goal("goal:"+intent.id, intent.id, desired, "required semantic outcome is true",
                ("destination completion predicates become true",), (intent.id,))

def define_constraints(intent: Intent) -> tuple[Constraint, ...]:
    return tuple(Constraint(f"constraint:{intent.id}:{i}", intent.id, c, "trajectory", "required", "always", "trajectory invalidated")
                 for i, c in enumerate(intent.constraints))

def define_destination(goal: Goal, constraints: tuple[Constraint, ...]) -> DestinationContract:
    return DestinationContract("destination:"+goal.id, goal.id, goal.desired_outcome,
                               ("required final semantic state",), ("completion evidence",),
                               constraints, ("required final state is true",), ("blocking failure is true",),
                               ("evaluate all completion predicates",))

def evaluate_transition(
    *,
    invalidated: bool = False,
    blocked: bool = False,
    undetermined: bool = False,
    should_validate: bool = False,
    should_replan: bool = False,
) -> TransitionEvaluation:
    if invalidated:
        decision = EvaluationDecision.INVALIDATED
    elif blocked:
        decision = EvaluationDecision.BLOCKED
    elif undetermined:
        decision = EvaluationDecision.UNDETERMINED
    elif should_validate:
        decision = EvaluationDecision.VALIDATE
    elif should_replan:
        decision = EvaluationDecision.REPLAN
    else:
        decision = EvaluationDecision.CONTINUE
    return TransitionEvaluation("evaluation", decision, (decision.value,), "evaluated", "evaluated", "evaluated", "evaluated")

def validate_destination(
    destination: DestinationContract,
    *,
    required_outcome_satisfied: bool,
    final_state_satisfied: bool,
    required_evidence_satisfied: bool,
    constraints_satisfied: bool,
    completion_conditions_satisfied: bool,
    failure_conditions_triggered: bool = False,
    unresolved_contradictions: tuple[str, ...] = (),
    evidence: tuple[Evidence, ...] = (),
) -> DestinationValidation:
    if not all((required_outcome_satisfied, final_state_satisfied, required_evidence_satisfied,
                constraints_satisfied, completion_conditions_satisfied)) or failure_conditions_triggered or unresolved_contradictions:
        if not constraints_satisfied:
            outcome = TerminalStatus.BLOCKED
        elif failure_conditions_triggered:
            outcome = TerminalStatus.INVALIDATED
        elif unresolved_contradictions or not required_evidence_satisfied:
            outcome = TerminalStatus.UNDETERMINED
        else:
            outcome = TerminalStatus.NOT_REACHED
    else:
        outcome = TerminalStatus.REACHED
    return DestinationValidation(destination.id, required_outcome_satisfied, final_state_satisfied,
                                 required_evidence_satisfied, constraints_satisfied,
                                 completion_conditions_satisfied, failure_conditions_triggered,
                                 unresolved_contradictions, tuple(evidence), outcome)
