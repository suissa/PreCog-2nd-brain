import pytest

from intent_trajectory.branches import (
    BranchObservation,
    Scenario,
    assert_scenarios,
    classify_branch,
    evaluate_scenario,
    run_scenarios,
)
from intent_trajectory.domain import BranchClass


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        (BranchObservation(progressed=True), BranchClass.VALID_PROGRESS),
        (BranchObservation(no_progress=True), BranchClass.VALID_NO_PROGRESS),
        (BranchObservation(recovered=True), BranchClass.VALID_RECOVERY),
        (BranchObservation(terminal=True), BranchClass.VALID_TERMINAL),
        (BranchObservation(input_valid=False), BranchClass.INVALID_INPUT),
        (BranchObservation(state_valid=False), BranchClass.INVALID_STATE),
        (BranchObservation(transition_valid=False), BranchClass.INVALID_TRANSITION),
        (BranchObservation(evidence_valid=False), BranchClass.INVALID_EVIDENCE),
        (BranchObservation(constraint_valid=False), BranchClass.INVALID_CONSTRAINT),
        (BranchObservation(destination_valid=False), BranchClass.INVALID_DESTINATION),
        (BranchObservation(termination_valid=False), BranchClass.INVALID_TERMINATION),
    ],
)
def test_every_step03_branch_class_is_executable(
    observation: BranchObservation, expected: BranchClass
) -> None:
    decision = classify_branch(observation)
    assert decision.branch is expected
    assert decision.valid is expected.name.startswith("VALID_")


def test_invalid_precedence_is_deterministic() -> None:
    decision = classify_branch(
        BranchObservation(
            input_valid=False,
            state_valid=False,
            transition_valid=False,
            evidence_valid=False,
            constraint_valid=False,
            destination_valid=False,
            termination_valid=False,
            terminal=True,
        )
    )
    assert decision.branch is BranchClass.INVALID_INPUT
    assert decision.precedence == 1


def test_valid_precedence_is_deterministic() -> None:
    decision = classify_branch(
        BranchObservation(
            progressed=True,
            recovered=True,
            terminal=True,
            no_progress=True,
        )
    )
    assert decision.branch is BranchClass.VALID_TERMINAL


def test_invalid_scenario_fails_closed() -> None:
    decision = classify_branch(BranchObservation())
    assert decision.branch is BranchClass.INVALID_INPUT
    assert not decision.valid


def test_scenario_result_is_observable() -> None:
    result = evaluate_scenario(
        Scenario(
            "terminal-success",
            BranchObservation(terminal=True, reason="destination validated"),
            BranchClass.VALID_TERMINAL,
        )
    )
    assert result.passed
    assert result.decision.reason == "destination validated"


def test_scenario_engine_runs_complete_matrix() -> None:
    scenarios = tuple(
        Scenario(
            branch.value,
            BranchObservation(
                **(
                    {"progressed": True}
                    if branch is BranchClass.VALID_PROGRESS
                    else {"no_progress": True}
                    if branch is BranchClass.VALID_NO_PROGRESS
                    else {"recovered": True}
                    if branch is BranchClass.VALID_RECOVERY
                    else {"terminal": True}
                    if branch is BranchClass.VALID_TERMINAL
                    else {
                        {
                            BranchClass.INVALID_INPUT: "input_valid",
                            BranchClass.INVALID_STATE: "state_valid",
                            BranchClass.INVALID_TRANSITION: "transition_valid",
                            BranchClass.INVALID_EVIDENCE: "evidence_valid",
                            BranchClass.INVALID_CONSTRAINT: "constraint_valid",
                            BranchClass.INVALID_DESTINATION: "destination_valid",
                            BranchClass.INVALID_TERMINATION: "termination_valid",
                        }[branch]: False
                    }
                )
            ),
            branch,
        )
        for branch in BranchClass
    )
    results = run_scenarios(scenarios)
    assert len(results) == len(BranchClass)
    assert all(result.passed for result in results)
    assert_scenarios(scenarios)
