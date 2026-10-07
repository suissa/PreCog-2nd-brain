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
