from datetime import datetime, timezone
from intent_trajectory.domain import Intent, Provenance, EvaluationDecision, TerminalStatus
from intent_trajectory.pipeline import understand, normalize, contextualize, define_goal, define_constraints, define_destination, evaluate_transition, validate_destination

NOW = datetime.now(timezone.utc)
def intent() -> Intent:
    return Intent("i1", "book appointment", Provenance("i1","test",NOW,"unit"), NOW, requested_outcome="appointment booked")

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
    e = evaluate_transition(invalidated=True, blocked=True, undetermined=True, should_validate=True, should_replan=True)
    assert e.decision is EvaluationDecision.INVALIDATED

def test_destination_reached() -> None:
    d = define_destination(define_goal(contextualize(normalize(understand(intent())), ()), intent()), ())
    v = validate_destination(d, required_outcome_satisfied=True, final_state_satisfied=True,
                             required_evidence_satisfied=True, constraints_satisfied=True,
                             completion_conditions_satisfied=True)
    assert v.outcome is TerminalStatus.REACHED

def test_execute_transition_reconstructs_semantic_state_and_evidence() -> None:
    from intent_trajectory.domain import Provenance, SemanticState, Transition, TransitionStatus, ConditionStatus
    from intent_trajectory.pipeline import execute_transition
    p = Provenance("source-1", "test", NOW, "unit")
    state = SemanticState("s0", ("customer known",), (), (p,))
    t = Transition("t1", "s0", "book appointment", ("customer known",),
                   (), ("appointment booked",), ("appointment booked",))
    result = execute_transition(t, state, observed_facts=("appointment booked",), provenance=p, temporal_position=NOW)
    assert result.status is TransitionStatus.SUCCEEDED
    assert result.resulting_state.predecessor_state_id == "s0"
    assert result.resulting_state.conditions == (("appointment booked", ConditionStatus.TRUE),)
    assert len(result.evidence) == 1

def test_execute_transition_preserves_unknown_and_contradiction() -> None:
    from intent_trajectory.domain import Provenance, SemanticState, Transition, TransitionStatus, ConditionStatus
    from intent_trajectory.pipeline import execute_transition
    p = Provenance("source-2", "test", NOW, "unit")
    state = SemanticState("s0", (), (), (p,))
    t = Transition("t2", "s0", "book appointment", ("customer known",),
                   (), ("appointment booked",), ("appointment booked",))
    result = execute_transition(t, state, observed_facts=(), provenance=p,
                                temporal_position=NOW, contradicted_facts=("appointment booked",))
    assert result.status is TransitionStatus.UNDETERMINED
    assert result.unresolved_conditions == ()
    assert result.resulting_state.conditions == (("appointment booked", ConditionStatus.UNKNOWN),)
    assert result.resulting_state.contradictions == ("appointment booked",)
