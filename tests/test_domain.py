from datetime import datetime, timezone
import pytest
from intent_trajectory.domain import (
    ConditionStatus, DestinationContract, DestinationValidation, Goal, Intent,
    Provenance, TerminalStatus, Transition, SemanticState,
)

NOW = datetime.now(timezone.utc)
PROV = Provenance("intent-1", "test", NOW, "unit")

def test_intent_is_immutable_and_validated() -> None:
    intent = Intent("i1", "book appointment", PROV, NOW, requested_outcome="appointment booked")
    with pytest.raises(Exception):
        intent.expression = "mutated"  # type: ignore[misc]

def test_unknown_is_explicit() -> None:
    state = SemanticState("s1", (), (("condition-1", ConditionStatus.UNKNOWN),), (PROV,))
    assert state.conditions[0][1] is ConditionStatus.UNKNOWN

def test_goal_is_semantic() -> None:
    goal = Goal("g1", "i1", "appointment booked", "booking exists", ("booking exists",), ("i1",))
    assert "tool" not in goal.desired_outcome.lower()

def test_transition_requires_semantic_change() -> None:
    with pytest.raises(ValueError):
        Transition("t1", "s1", "execute", (), (), (), ("done",))

def test_reached_requires_all_predicates() -> None:
    with pytest.raises(ValueError):
        DestinationValidation("d1", True, True, False, True, True, False, (), (), TerminalStatus.REACHED)
