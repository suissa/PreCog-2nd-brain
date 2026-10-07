from __future__ import annotations

from datetime import datetime, timezone

from .domain import (
    CandidateTrajectory,
    Constraint,
    ContextOutcome,
    ContextualizedIntent,
    DestinationContract,
    DestinationValidation,
    Evidence,
    EvaluationDecision,
    Goal,
    Intent,
    NormalizedIntent,
    OutcomeStatus,
    TerminalOutcome,
    Trajectory,
    TerminalStatus,
    TrajectoryStatus,
    Transition,
    TransitionEvaluation,
    TransitionResult,
    TransitionStatus,
    UnderstoodIntent,
    Provenance,
    SemanticState,
    ConditionStatus,
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
        return UnderstoodIntent(
            intent.id,
            intent.expression or "unresolved",
            OutcomeStatus.UNRESOLVABLE,
            desired_outcome=outcome,
            ambiguities=tuple(ambiguities),
            missing_information=tuple(missing),
        )
    if ambiguities:
        return UnderstoodIntent(
            intent.id,
            intent.expression,
            OutcomeStatus.NEEDS_CLARIFICATION,
            desired_outcome=outcome,
            ambiguities=tuple(ambiguities),
        )
    return UnderstoodIntent(
        intent.id,
        intent.expression,
        OutcomeStatus.UNDERSTOOD,
        desired_outcome=outcome,
        explicit_requirements=intent.explicit_requirements,
    )


def normalize(understood: UnderstoodIntent) -> NormalizedIntent:
    return NormalizedIntent(
        source_understood_intent_id=understood.source_intent_id,
        canonical_purpose=understood.desired_outcome or understood.interpretation,
        requirements=understood.explicit_requirements + understood.inferred_requirements,
        constraints=(),
        actor=understood.actor,
        entities=understood.entities,
        unresolved_ambiguities=understood.ambiguities,
        uncertainty=understood.uncertainty,
    )


def contextualize(
    normalized: NormalizedIntent,
    context: tuple[str, ...] = (),
) -> ContextualizedIntent:
    outcome = (
        ContextOutcome.CONTEXTUALIZED
        if not normalized.unresolved_ambiguities
        else ContextOutcome.CONTEXTUALLY_INCOMPLETE
    )
    return ContextualizedIntent(
        normalized.source_understood_intent_id,
        tuple(context),
        outcome,
        unresolved_context=normalized.unresolved_ambiguities,
    )


def define_goal(contextualized: ContextualizedIntent, intent: Intent) -> Goal:
    if contextualized.outcome != ContextOutcome.CONTEXTUALIZED:
        raise ValueError("cannot define Goal from incomplete context")
    desired = intent.requested_outcome or contextualized.normalized_intent_id
    return Goal(
        "goal:" + intent.id,
        intent.id,
        desired,
        "required semantic outcome is true",
        ("destination completion predicates become true",),
        (intent.id,),
    )


def define_constraints(intent: Intent) -> tuple[Constraint, ...]:
    return tuple(
        Constraint(
            f"constraint:{intent.id}:{i}",
            intent.id,
            c,
            "trajectory",
            "required",
            "always",
            "trajectory invalidated",
        )
        for i, c in enumerate(intent.constraints)
    )


def define_destination(
    goal: Goal,
    constraints: tuple[Constraint, ...],
) -> DestinationContract:
    return DestinationContract(
        "destination:" + goal.id,
        goal.id,
        goal.desired_outcome,
        ("required final semantic state",),
        ("completion evidence",),
        constraints,
        ("required final state is true",),
        ("blocking failure is true",),
        ("evaluate all completion predicates",),
    )


def evaluate_transition(
    *,
    invalidated: bool = False,
    blocked: bool = False,
    undetermined: bool = False,
    should_validate: bool = False,
    should_replan: bool = False,
) -> TransitionEvaluation:
    """Evaluate explicit semantic flags using the canonical precedence order."""
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
    return TransitionEvaluation(
        "evaluation",
        decision,
        (decision.value,),
        "evaluated",
        "evaluated",
        "evaluated",
        "evaluated",
    )


def evaluate_transition_result(
    result: TransitionResult,
    *,
    constraint_violations: tuple[str, ...] = (),
    destination_may_be_complete: bool = False,
    replan_required: bool = False,
) -> TransitionEvaluation:
    """Derive a decision from a TransitionResult without declaring Destination success."""
    violations = tuple(dict.fromkeys(result.constraint_violations + constraint_violations))
    if violations:
        decision = EvaluationDecision.INVALIDATED
        reason = ("constraint violation",) + violations
    elif result.status is TransitionStatus.BLOCKED:
        decision = EvaluationDecision.BLOCKED
        reason = ("transition blocked",)
    elif (
        result.status is TransitionStatus.UNDETERMINED
        or result.contradictions
        or result.unresolved_conditions
    ):
        decision = EvaluationDecision.UNDETERMINED
        reason = ("critical evidence or state is unresolved",)
    elif result.status is TransitionStatus.FAILED:
        decision = EvaluationDecision.REPLAN
        reason = ("current transition cannot produce the required progress",)
    elif destination_may_be_complete:
        decision = EvaluationDecision.VALIDATE
        reason = ("transition may satisfy destination predicates",)
    elif replan_required:
        decision = EvaluationDecision.REPLAN
        reason = ("current transition requires replanning",)
    else:
        decision = EvaluationDecision.CONTINUE
        reason = ("semantic progress remains possible",)

    state_assessment = result.status.value
    evidence_assessment = (
        "contradictory" if result.contradictions
        else "unresolved" if result.unresolved_conditions
        else "sufficient"
    )
    constraint_assessment = "violated" if violations else "satisfied"
    destination_assessment = (
        "candidate_for_validation" if destination_may_be_complete else "not_yet_validated"
    )
    return TransitionEvaluation(
        result.transition_id,
        decision,
        reason,
        state_assessment,
        evidence_assessment,
        constraint_assessment,
        destination_assessment,
        result.resulting_state.id,
    )


def replan(
    *,
    intent: Intent,
    goal: Goal,
    constraints: tuple[Constraint, ...],
    destination: DestinationContract,
    current_state: SemanticState,
    transitions: tuple[Transition, ...],
    reason: str,
    trajectory_status: TrajectoryStatus = TrajectoryStatus.ACTIVE,
) -> CandidateTrajectory:
    """Create a new candidate plan while preserving semantic identity."""
    if trajectory_status is not TrajectoryStatus.ACTIVE:
        raise ValueError("cannot replan a terminal trajectory")
    if goal.source_intent_id != intent.id:
        raise ValueError("goal is not traceable to the original Intent")
    if destination.goal_id != goal.id:
        raise ValueError("Destination is not traceable to the original Goal")
    if tuple(destination.constraints) != tuple(constraints):
        raise ValueError("replan cannot silently change active Constraints")
    if not reason.strip():
        raise ValueError("replan reason must be explicit")

    candidate_id = f"trajectory:{intent.id}:replan:{current_state.id}"
    return CandidateTrajectory(
        id=candidate_id,
        origin_state_id=current_state.id,
        destination_id=destination.id,
        transitions=transitions,
        dependencies=(reason,),
        alternatives=tuple(t.id for t in transitions),
    )


def terminalize(
    trajectory: Trajectory,
    validation: DestinationValidation,
    *,
    evidence: tuple[Evidence, ...],
    satisfied_conditions: tuple[str, ...],
    unsatisfied_conditions: tuple[str, ...],
    constraint_status: str,
    reason: tuple[str, ...],
    provenance: Provenance,
) -> TerminalOutcome:
    """Materialize a terminal outcome only from an explicit DestinationValidation."""
    if validation.destination_id != trajectory.destination_id:
        raise ValueError("validation does not belong to trajectory Destination")
    if not reason:
        raise ValueError("terminalization requires an explicit reason")
    if not evidence:
        raise ValueError("terminalization requires evidence")
    if trajectory.status is not TrajectoryStatus.ACTIVE:
        raise ValueError("trajectory is already terminal")
    if validation.outcome is TerminalStatus.REACHED and (
        not validation.required_outcome_satisfied
        or not validation.final_state_satisfied
        or not validation.required_evidence_satisfied
        or not validation.constraints_satisfied
        or not validation.completion_conditions_satisfied
        or validation.failure_conditions_triggered
        or validation.unresolved_contradictions
    ):
        raise ValueError("Reached cannot be terminalized without every completion predicate")
    return TerminalOutcome(
        trajectory_id=trajectory.id,
        destination_id=trajectory.destination_id,
        status=validation.outcome,
        final_state_id=trajectory.current_state_id,
        evidence_ids=tuple(e.id for e in evidence),
        satisfied_conditions=satisfied_conditions,
        unsatisfied_conditions=unsatisfied_conditions,
        constraint_status=constraint_status,
        reason=reason,
        provenance=provenance,
    )


def apply_terminal_outcome(
    trajectory: Trajectory,
    terminal: TerminalOutcome,
) -> Trajectory:
    """Close an active trajectory exactly once using its validated terminal outcome."""
    if trajectory.status is not TrajectoryStatus.ACTIVE:
        raise ValueError("trajectory is already terminal")
    if terminal.trajectory_id != trajectory.id:
        raise ValueError("terminal outcome does not belong to trajectory")
    if terminal.destination_id != trajectory.destination_id:
        raise ValueError("terminal outcome does not belong to trajectory Destination")
    return Trajectory(
        id=trajectory.id,
        intent_id=trajectory.intent_id,
        goal_id=trajectory.goal_id,
        destination_id=trajectory.destination_id,
        current_state_id=trajectory.current_state_id,
        plan_ids=trajectory.plan_ids,
        transition_ids=trajectory.transition_ids,
        evidence_ids=tuple(dict.fromkeys(trajectory.evidence_ids + terminal.evidence_ids)),
        status=TrajectoryStatus(terminal.status.value),
        version=trajectory.version + 1,
        provenance=terminal.provenance,
    )


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
    if (
        not all(
            (
                required_outcome_satisfied,
                final_state_satisfied,
                required_evidence_satisfied,
                constraints_satisfied,
                completion_conditions_satisfied,
            )
        )
        or failure_conditions_triggered
        or unresolved_contradictions
    ):
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
    return DestinationValidation(
        destination.id,
        required_outcome_satisfied,
        final_state_satisfied,
        required_evidence_satisfied,
        constraints_satisfied,
        completion_conditions_satisfied,
        failure_conditions_triggered,
        unresolved_contradictions,
        tuple(evidence),
        outcome,
    )


def execute_transition(
    transition: Transition,
    previous_state: SemanticState,
    *,
    observed_facts: tuple[str, ...],
    provenance: Provenance,
    temporal_position: datetime | None = None,
    contradicted_facts: tuple[str, ...] = (),
) -> TransitionResult:
    """Apply semantic evidence to one transition without declaring destination success."""
    if transition.from_state_id != previous_state.id:
        raise ValueError("transition origin does not match previous semantic state")
    observed = tuple(dict.fromkeys(observed_facts))
    contradictions = tuple(dict.fromkeys(contradicted_facts))
    satisfied = tuple(fact for fact in transition.expected_change if fact in observed)
    unresolved = tuple(
        fact
        for fact in transition.expected_change
        if fact not in observed and fact not in contradictions
    )
    when = temporal_position or datetime.now(timezone.utc)
    evidence = tuple(
        Evidence(
            id=f"evidence:{transition.id}:{index}",
            source_transition_id=transition.id,
            observed_fact=fact,
            temporal_position=when,
            provenance=provenance,
            supports=(fact,) if fact in transition.expected_change else (),
            contradicts=(fact,) if fact in contradictions else (),
        )
        for index, fact in enumerate(observed + contradictions)
    )
    if contradictions:
        status = (
            TransitionStatus.UNDETERMINED
            if not satisfied
            else TransitionStatus.PARTIALLY_SUCCEEDED
        )
    elif len(satisfied) == len(transition.expected_change):
        status = TransitionStatus.SUCCEEDED
    elif satisfied:
        status = TransitionStatus.PARTIALLY_SUCCEEDED
    else:
        status = TransitionStatus.FAILED
    resulting = SemanticState(
        id=f"state:{transition.id}",
        facts=tuple(dict.fromkeys(previous_state.facts + observed)),
        conditions=tuple(
            (
                fact,
                ConditionStatus.TRUE if fact in satisfied else ConditionStatus.UNKNOWN,
            )
            for fact in transition.expected_change
        ),
        provenance=previous_state.provenance + (provenance,),
        predecessor_state_id=previous_state.id,
        contradictions=tuple(
            dict.fromkeys(previous_state.contradictions + contradictions)
        ),
        temporal_position=when,
    )
    return TransitionResult(
        transition_id=transition.id,
        previous_state=previous_state,
        resulting_state=resulting,
        evidence=evidence,
        status=status,
        newly_satisfied_conditions=satisfied,
        unresolved_conditions=unresolved,
        contradictions=contradictions,
    )


def reconstruct_state(
    previous_state: SemanticState,
    transition: Transition,
    evidence: tuple[Evidence, ...],
) -> SemanticState:
    """Rebuild the semantic state from a predecessor and immutable Evidence."""
    if transition.from_state_id != previous_state.id:
        raise ValueError("transition origin does not match previous semantic state")
    if not evidence:
        raise ValueError("state reconstruction requires evidence")

    transition_evidence = tuple(
        item for item in evidence if item.source_transition_id == transition.id
    )
    if not transition_evidence:
        raise ValueError("evidence does not belong to transition")

    observed = tuple(
        dict.fromkeys(
            item.observed_fact
            for item in transition_evidence
            if item.observed_fact
        )
    )
    contradictions = tuple(
        dict.fromkeys(
            previous_state.contradictions
            + tuple(
                fact
                for item in transition_evidence
                for fact in item.contradicts
            )
        )
    )
    satisfied = tuple(
        fact for fact in transition.expected_change
        if fact in observed and fact not in contradictions
    )

    return SemanticState(
        id=f"state:{transition.id}",
        facts=tuple(dict.fromkeys(previous_state.facts + observed)),
        conditions=tuple(
            (
                fact,
                ConditionStatus.TRUE
                if fact in satisfied
                else ConditionStatus.UNKNOWN,
            )
            for fact in transition.expected_change
        ),
        provenance=previous_state.provenance
        + tuple(item.provenance for item in transition_evidence),
        predecessor_state_id=previous_state.id,
        contradictions=contradictions,
        temporal_position=max(
            item.temporal_position for item in transition_evidence
        ),
    )
