"""Canonical STEP-03/04 scenario coverage."""
from dataclasses import dataclass
from datetime import datetime, timezone
import pytest

from intent_trajectory.domain import (
    BranchClass, ConditionStatus, DestinationContract, Evidence,
    EvaluationDecision, Provenance, SemanticState, TerminalStatus,
    Transition, TransitionResult, TransitionStatus,
)
from intent_trajectory.pipeline import evaluate_transition_result, validate_destination
from intent_trajectory.branches import BranchObservation, classify_branch

NOW = datetime.now(timezone.utc)


@dataclass(frozen=True)
class ScenarioCase:
    id: str
    stage: str
    branch: BranchClass
    expected_outcome: str
    invariant: str


CASES = (
    ScenarioCase("progress", "transition", BranchClass.VALID_PROGRESS, "Continue", "I12"),
    ScenarioCase("no-progress", "transition", BranchClass.VALID_NO_PROGRESS, "Continue", "I7"),
    ScenarioCase("recovery", "transition", BranchClass.VALID_RECOVERY, "Replan", "I15"),
    ScenarioCase("terminal", "destination", BranchClass.VALID_TERMINAL, "Reached", "I14"),
    ScenarioCase("invalid-input", "input", BranchClass.INVALID_INPUT, "reject", "I19"),
    ScenarioCase("invalid-state", "state", BranchClass.INVALID_STATE, "reject", "I12"),
    ScenarioCase("invalid-transition", "transition", BranchClass.INVALID_TRANSITION, "reject", "I7"),
    ScenarioCase("invalid-evidence", "evidence", BranchClass.INVALID_EVIDENCE, "reject", "I2"),
    ScenarioCase("invalid-constraint", "constraint", BranchClass.INVALID_CONSTRAINT, "Invalidated", "I6"),
    ScenarioCase("invalid-destination", "destination", BranchClass.INVALID_DESTINATION, "reject", "I4"),
    ScenarioCase("invalid-termination", "termination", BranchClass.INVALID_TERMINATION, "reject", "I17"),
)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_step04_branch_matrix_is_observable(case: ScenarioCase) -> None:
    if case.branch is BranchClass.VALID_PROGRESS:
        observation = BranchObservation(progressed=True)
    elif case.branch is BranchClass.VALID_NO_PROGRESS:
        observation = BranchObservation(no_progress=True)
    elif case.branch is BranchClass.VALID_RECOVERY:
        observation = BranchObservation(recovered=True)
    elif case.branch is BranchClass.VALID_TERMINAL:
        observation = BranchObservation(terminal=True)
    else:
        names = {
            BranchClass.INVALID_INPUT: "input_valid",
            BranchClass.INVALID_STATE: "state_valid",
            BranchClass.INVALID_TRANSITION: "transition_valid",
            BranchClass.INVALID_EVIDENCE: "evidence_valid",
            BranchClass.INVALID_CONSTRAINT: "constraint_valid",
            BranchClass.INVALID_DESTINATION: "destination_valid",
            BranchClass.INVALID_TERMINATION: "termination_valid",
        }
        observation = BranchObservation(**{names[case.branch]: False})
    assert classify_branch(observation).branch is case.branch


def _destination() -> DestinationContract:
    return DestinationContract(
        "d1", "g1", "done", ("final",), ("evidence",), (),
        ("complete",), ("failed",), ("validate",)
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(required_outcome_satisfied=False, final_state_satisfied=False,
              required_evidence_satisfied=True, constraints_satisfied=True,
              completion_conditions_satisfied=False), TerminalStatus.NOT_REACHED),
        (dict(required_outcome_satisfied=False, final_state_satisfied=False,
              required_evidence_satisfied=True, constraints_satisfied=False,
              completion_conditions_satisfied=False), TerminalStatus.BLOCKED),
        (dict(required_outcome_satisfied=False, final_state_satisfied=False,
              required_evidence_satisfied=True, constraints_satisfied=True,
              completion_conditions_satisfied=False, failure_conditions_triggered=True),
         TerminalStatus.INVALIDATED),
        (dict(required_outcome_satisfied=True, final_state_satisfied=True,
              required_evidence_satisfied=False, constraints_satisfied=True,
              completion_conditions_satisfied=True), TerminalStatus.UNDETERMINED),
    ],
)
def test_each_non_reached_terminal_outcome(kwargs, expected) -> None:
    assert validate_destination(_destination(), **kwargs).outcome is expected


def test_reached_requires_all_predicates_and_evidence() -> None:
    p = Provenance("p", "test", NOW, "unit")
    evidence = Evidence("e", "t", "complete", NOW, p, supports=("complete",))
    validation = validate_destination(
        _destination(), True, True, True, True, True, evidence=(evidence,)
    )
    assert validation.outcome is TerminalStatus.REACHED


@pytest.mark.parametrize("missing", [
    "required_outcome_satisfied", "final_state_satisfied",
    "required_evidence_satisfied", "constraints_satisfied",
    "completion_conditions_satisfied",
])
def test_reached_rejects_missing_completion_predicate(missing: str) -> None:
    p = Provenance("p", "test", NOW, "unit")
    kwargs = dict(
        required_outcome_satisfied=True, final_state_satisfied=True,
        required_evidence_satisfied=True, constraints_satisfied=True,
        completion_conditions_satisfied=True,
        failure_conditions_triggered=False, unresolved_contradictions=(),
        evidence=(Evidence("e", "t", "complete", NOW, p),),
    )
    kwargs[missing] = False
    with pytest.raises(ValueError, match="Reached"):
        from intent_trajectory.domain import DestinationValidation
        DestinationValidation("d1", outcome=TerminalStatus.REACHED, **kwargs)


def test_unknown_never_becomes_reached() -> None:
    p = Provenance("p", "test", NOW, "unit")
    state = SemanticState("s1", (), (("complete", ConditionStatus.UNKNOWN),), (p,))
    assert state.conditions[0][1] is ConditionStatus.UNKNOWN
    validation = validate_destination(_destination(), True, False, True, True, False)
    assert validation.outcome is TerminalStatus.NOT_REACHED


def test_action_success_is_not_destination_success() -> None:
    p = Provenance("p", "test", NOW, "unit")
    state = SemanticState("s0", (), (), (p,))
    transition = Transition("t", "s0", "do", ("ready",), (), ("complete",), ("complete",))
    result = TransitionResult(
        "t", state, SemanticState("s1", ("complete",), (), (p,), "s0"),
        (Evidence("e", "t", "complete", NOW, p),), TransitionStatus.SUCCEEDED
    )
    evaluation = evaluate_transition_result(result, destination_may_be_complete=True)
    assert evaluation.decision is EvaluationDecision.VALIDATE


def test_contradiction_blocks_reached() -> None:
    p = Provenance("p", "test", NOW, "unit")
    validation = validate_destination(
        _destination(), True, True, True, True, True,
        unresolved_contradictions=("complete",),
        evidence=(Evidence("e", "t", "complete", NOW, p),),
    )
    assert validation.outcome is TerminalStatus.UNDETERMINED
