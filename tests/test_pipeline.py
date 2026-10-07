from datetime import datetime, timezone

import pytest

from intent_trajectory.domain import (
    CandidateTrajectory,
    ConditionStatus,
    Constraint,
    EvaluationDecision,
    Intent,
    Provenance,
    SemanticState,
    TerminalStatus,
    Trajectory, TrajectoryStatus,
    Transition,
    TransitionStatus, Goal, DestinationContract,
)
from intent_trajectory.pipeline import (
    contextualize,
    define_constraints,
    define_destination,
    define_goal,
    evaluate_transition,
    evaluate_transition_result,
    execute_transition,
    normalize,
    replan,
    understand,
    validate_destination,
)

NOW = datetime.now(timezone.utc)


def intent() -> Intent:
    return Intent(
        "i1",
        "book appointment",
        Provenance("i1", "test", NOW, "unit"),
        NOW,
        requested_outcome="appointment booked",
    )


def make_transition(
    transition_id: str = "t1",
    state_id: str = "s0",
) -> Transition:
    return Transition(
        transition_id,
        state_id,
        "book appointment",
        ("customer known",),
        (),
        ("appointment booked",),
        ("appointment booked",),
    )


def make_state(state_id: str = "s0") -> SemanticState:
    return SemanticState(state_id, ("customer known",), (), (Provenance("state", "test", NOW, "unit"),))


def make_destination() -> tuple[Intent, Goal, tuple[Constraint, ...], DestinationContract, tuple[Constraint, ...]]:
    i = intent()
    u = understand(i)
    n = normalize(u)
    c = contextualize(n, ())
    g = define_goal(c, i)
    constraints = define_constraints(i)
    d = define_destination(g, constraints)
    return i, g, constraints, d, constraints


def test_semantic_pipeline() -> None:
    i = intent()
    u = understand(i)
    n = normalize(u)
    c = contextualize(n, ("customer is authenticated",))
    g = define_goal(c, i)
    cs = define_constraints(i)
    d = define_destination(g, cs)
    assert d.goal_id == g.id


def test_evaluation_precedence() -> None:
    e = evaluate_transition(
        invalidated=True,
        blocked=True,
        undetermined=True,
        should_validate=True,
        should_replan=True,
    )
    assert e.decision is EvaluationDecision.INVALIDATED


def test_destination_reached() -> None:
    d = define_destination(
        define_goal(contextualize(normalize(understand(intent())), ()), intent()),
        (),
    )
    v = validate_destination(
        d,
        required_outcome_satisfied=True,
        final_state_satisfied=True,
        required_evidence_satisfied=True,
        constraints_satisfied=True,
        completion_conditions_satisfied=True,
    )
    assert v.outcome is TerminalStatus.REACHED


def test_execute_transition_reconstructs_semantic_state_and_evidence() -> None:
    p = Provenance("source-1", "test", NOW, "unit")
    state = SemanticState("s0", ("customer known",), (), (p,))
    t = make_transition()
    result = execute_transition(
        t,
        state,
        observed_facts=("appointment booked",),
        provenance=p,
        temporal_position=NOW,
    )
    assert result.status is TransitionStatus.SUCCEEDED
    assert result.resulting_state.predecessor_state_id == "s0"
    assert result.resulting_state.conditions == (("appointment booked", ConditionStatus.TRUE),)
    assert len(result.evidence) == 1


def test_execute_transition_preserves_unknown_and_contradiction() -> None:
    p = Provenance("source-2", "test", NOW, "unit")
    state = SemanticState("s0", (), (), (p,))
    t = make_transition()
    result = execute_transition(
        t,
        state,
        observed_facts=(),
        provenance=p,
        temporal_position=NOW,
        contradicted_facts=("appointment booked",),
    )
    assert result.status is TransitionStatus.UNDETERMINED
    assert result.unresolved_conditions == ()
    assert result.resulting_state.conditions == (("appointment booked", ConditionStatus.UNKNOWN),)
    assert result.resulting_state.contradictions == ("appointment booked",)


def test_evaluate_transition_result_preserves_precedence() -> None:
    p = Provenance("source-3", "test", NOW, "unit")
    result = execute_transition(
        make_transition(),
        make_state(),
        observed_facts=(),
        provenance=p,
        temporal_position=NOW,
        contradicted_facts=("appointment booked",),
    )
    evaluation = evaluate_transition_result(
        result,
        constraint_violations=("constraint:c1",),
        destination_may_be_complete=True,
        replan_required=True,
    )
    assert evaluation.transition_id == "t1"
    assert evaluation.decision is EvaluationDecision.INVALIDATED
    assert evaluation.next_state_id == result.resulting_state.id


def test_evaluate_transition_result_blocks_blocked_transition() -> None:
    state = make_state()
    t = make_transition()
    from intent_trajectory.domain import TransitionResult
    blocked = TransitionResult(
        transition_id=t.id,
        previous_state=state,
        resulting_state=SemanticState("state:t1", state.facts, (), state.provenance, state.id),
        evidence=(),
        status=TransitionStatus.BLOCKED,
        unresolved_conditions=("appointment booked",),
    )
    evaluation = evaluate_transition_result(blocked)
    assert evaluation.decision is EvaluationDecision.BLOCKED


def test_evaluate_transition_result_marks_undetermined() -> None:
    p = Provenance("source-undetermined", "test", NOW, "unit")
    result = execute_transition(
        make_transition(),
        make_state(),
        observed_facts=(),
        provenance=p,
        temporal_position=NOW,
        contradicted_facts=("appointment booked",),
    )
    evaluation = evaluate_transition_result(result)
    assert evaluation.decision is EvaluationDecision.UNDETERMINED


def test_evaluate_transition_result_continues_progress() -> None:
    p = Provenance("source-progress", "test", NOW, "unit")
    t = Transition(
        "t-progress",
        "s0",
        "observe appointment availability",
        ("customer known",),
        (),
        ("availability checked",),
        ("availability checked",),
    )
    result = execute_transition(
        t,
        make_state(),
        observed_facts=("availability checked",),
        provenance=p,
        temporal_position=NOW,
    )
    evaluation = evaluate_transition_result(result)
    assert evaluation.decision is EvaluationDecision.CONTINUE


def test_evaluate_transition_result_replans_failed_transition() -> None:
    p = Provenance("source-4", "test", NOW, "unit")
    result = execute_transition(
        make_transition(),
        make_state(),
        observed_facts=(),
        provenance=p,
        temporal_position=NOW,
    )
    evaluation = evaluate_transition_result(result)
    assert result.status is TransitionStatus.FAILED
    assert evaluation.decision is EvaluationDecision.REPLAN


def test_evaluate_transition_result_validates_possible_completion() -> None:
    p = Provenance("source-5", "test", NOW, "unit")
    result = execute_transition(
        make_transition(),
        make_state(),
        observed_facts=("appointment booked",),
        provenance=p,
        temporal_position=NOW,
    )
    evaluation = evaluate_transition_result(result, destination_may_be_complete=True)
    assert evaluation.decision is EvaluationDecision.VALIDATE


def test_replan_preserves_semantic_identity() -> None:
    i, g, constraints, d, _ = make_destination()
    state = make_state()
    replacement = make_transition("t2")
    candidate = replan(
        intent=i,
        goal=g,
        constraints=constraints,
        destination=d,
        current_state=state,
        transitions=(replacement,),
        reason="original transition failed",
    )
    assert isinstance(candidate, CandidateTrajectory)
    assert candidate.destination_id == d.id
    assert d.goal_id == g.id
    assert g.source_intent_id == i.id
    assert tuple(d.constraints) == constraints
    assert candidate.origin_state_id == state.id


def test_replan_rejects_semantic_mutation() -> None:
    i, g, constraints, d, _ = make_destination()
    state = make_state()
    other = Intent(
        "i2",
        "cancel appointment",
        Provenance("i2", "test", NOW, "unit"),
        NOW,
        requested_outcome="appointment cancelled",
    )
    with pytest.raises(ValueError, match="original Intent"):
        replan(
            intent=other,
            goal=g,
            constraints=constraints,
            destination=d,
            current_state=state,
            transitions=(make_transition("t2"),),
            reason="changed objective",
        )

    altered_constraints = (
        Constraint(
            "constraint:altered",
            i.id,
            "not allowed",
            "trajectory",
            "required",
            "always",
            "trajectory invalidated",
        ),
    )
    with pytest.raises(ValueError, match="active Constraints"):
        replan(
            intent=i,
            goal=g,
            constraints=altered_constraints,
            destination=d,
            current_state=state,
            transitions=(make_transition("t2"),),
            reason="changed constraints",
        )


def test_replan_rejects_terminal_trajectory() -> None:
    i, g, constraints, d, _ = make_destination()
    with pytest.raises(ValueError, match="terminal trajectory"):
        replan(
            intent=i,
            goal=g,
            constraints=constraints,
            destination=d,
            current_state=make_state(),
            transitions=(make_transition("t2"),),
            reason="attempted post-terminal action",
            trajectory_status=TrajectoryStatus.REACHED,
        )


def make_trajectory() -> tuple[Trajectory, Intent, Goal, tuple[Constraint, ...], DestinationContract]:
    i, g, constraints, d, _ = make_destination()
    trajectory = Trajectory(
        id="trajectory:i1:1",
        intent_id=i.id,
        goal_id=g.id,
        destination_id=d.id,
        current_state_id="s0",
        plan_ids=("plan:1",),
        transition_ids=("t1",),
        evidence_ids=(),
        status=TrajectoryStatus.ACTIVE,
        version=1,
        provenance=i.provenance,
    )
    return trajectory, i, g, constraints, d


def test_terminalize_requires_destination_validation_and_evidence() -> None:
    from intent_trajectory.domain import Evidence
    from intent_trajectory.pipeline import terminalize
    trajectory, i, _, _, d = make_trajectory()
    validation = validate_destination(
        d,
        required_outcome_satisfied=True,
        final_state_satisfied=True,
        required_evidence_satisfied=True,
        constraints_satisfied=True,
        completion_conditions_satisfied=True,
    )
    evidence = Evidence("e1", "t1", "appointment booked", NOW, i.provenance, supports=("appointment booked",))
    terminal = terminalize(
        trajectory,
        validation,
        evidence=(evidence,),
        satisfied_conditions=("appointment booked",),
        unsatisfied_conditions=(),
        constraint_status="satisfied",
        reason=("all destination predicates validated",),
        provenance=i.provenance,
    )
    assert terminal.status is TerminalStatus.REACHED
    assert terminal.destination_id == d.id


def test_terminalize_rejects_already_terminal_trajectory() -> None:
    from intent_trajectory.domain import Evidence, Trajectory
    from intent_trajectory.pipeline import terminalize
    trajectory, i, g, constraints, d = make_trajectory()
    terminal_trajectory = Trajectory(
        trajectory.id, i.id, g.id, d.id, trajectory.current_state_id,
        trajectory.plan_ids, trajectory.transition_ids, (), TrajectoryStatus.REACHED, 2, i.provenance
    )
    validation = validate_destination(
        d,
        required_outcome_satisfied=True,
        final_state_satisfied=True,
        required_evidence_satisfied=True,
        constraints_satisfied=True,
        completion_conditions_satisfied=True,
    )
    evidence = Evidence("e2", "t1", "appointment booked", NOW, i.provenance, supports=("appointment booked",))
    with pytest.raises(ValueError, match="already terminal"):
        terminalize(
            terminal_trajectory, validation, evidence=(evidence,),
            satisfied_conditions=("appointment booked",), unsatisfied_conditions=(),
            constraint_status="satisfied", reason=("duplicate terminalization",),
            provenance=i.provenance,
        )


def test_apply_terminal_outcome_closes_trajectory_once() -> None:
    from intent_trajectory.domain import Evidence
    from intent_trajectory.pipeline import apply_terminal_outcome, terminalize
    trajectory, i, _, _, d = make_trajectory()
    validation = validate_destination(
        d,
        required_outcome_satisfied=True,
        final_state_satisfied=True,
        required_evidence_satisfied=True,
        constraints_satisfied=True,
        completion_conditions_satisfied=True,
    )
    evidence = Evidence("e3", "t1", "appointment booked", NOW, i.provenance, supports=("appointment booked",))
    terminal = terminalize(
        trajectory, validation, evidence=(evidence,),
        satisfied_conditions=("appointment booked",), unsatisfied_conditions=(),
        constraint_status="satisfied", reason=("validated",), provenance=i.provenance,
    )
    closed = apply_terminal_outcome(trajectory, terminal)
    assert closed.status is TrajectoryStatus.REACHED
    assert closed.version == 2
    assert closed.evidence_ids == ("e3",)
    with pytest.raises(ValueError, match="already terminal"):
        apply_terminal_outcome(closed, terminal)


def test_reconstruct_state_from_evidence_is_deterministic() -> None:
    from intent_trajectory.domain import Evidence
    from intent_trajectory.pipeline import reconstruct_state

    p = Provenance("source-reconstruct", "test", NOW, "unit")
    state = make_state()
    transition = make_transition("t-reconstruct")
    evidence = (
        Evidence(
            "e1",
            transition.id,
            "appointment booked",
            NOW,
            p,
            supports=("appointment booked",),
        ),
    )
    first = reconstruct_state(state, transition, evidence)
    second = reconstruct_state(state, transition, evidence)
    assert first == second
    assert first.predecessor_state_id == state.id
    assert first.conditions == (("appointment booked", ConditionStatus.TRUE),)


def test_reconstruct_state_preserves_contradiction_and_unknown() -> None:
    from intent_trajectory.domain import Evidence
    from intent_trajectory.pipeline import reconstruct_state

    p = Provenance("source-reconstruct-contradiction", "test", NOW, "unit")
    state = make_state()
    transition = make_transition("t-reconstruct-contradiction")
    evidence = (
        Evidence(
            "e1",
            transition.id,
            "appointment booked",
            NOW,
            p,
            contradicts=("appointment booked",),
        ),
    )
    rebuilt = reconstruct_state(state, transition, evidence)
    assert rebuilt.conditions == (("appointment booked", ConditionStatus.UNKNOWN),)
    assert rebuilt.contradictions == ("appointment booked",)


def test_reconstruct_state_rejects_missing_evidence() -> None:
    from intent_trajectory.pipeline import reconstruct_state

    with pytest.raises(ValueError, match="requires evidence"):
        reconstruct_state(make_state(), make_transition("t-empty"), ())


def test_reconstruct_state_rejects_unrelated_evidence() -> None:
    from intent_trajectory.domain import Evidence
    from intent_trajectory.pipeline import reconstruct_state

    p = Provenance("source-reconstruct-unrelated", "test", NOW, "unit")
    evidence = (
        Evidence("e1", "other-transition", "unrelated", NOW, p),
    )
    with pytest.raises(ValueError, match="does not belong"):
        reconstruct_state(make_state(), make_transition("t-reconstruct"), evidence)
