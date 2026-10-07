from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .domain import BranchClass


@dataclass(frozen=True, slots=True)
class BranchObservation:
    """Observable predicates used to classify one STEP-03 execution branch.

    Invalid predicates always dominate valid outcomes. Among valid outcomes,
    terminal > recovery > progress > no-progress is deterministic.
    """

    input_valid: bool = True
    state_valid: bool = True
    transition_valid: bool = True
    evidence_valid: bool = True
    constraint_valid: bool = True
    destination_valid: bool = True
    termination_valid: bool = True

    progressed: bool = False
    recovered: bool = False
    terminal: bool = False
    no_progress: bool = False

    reason: str = ""

    def __post_init__(self) -> None:
        if self.reason and not self.reason.strip():
            raise ValueError("reason must be non-empty when supplied")


@dataclass(frozen=True, slots=True)
class BranchDecision:
    branch: BranchClass
    valid: bool
    reason: str
    precedence: int


_INVALID_PRECEDENCE: tuple[tuple[str, BranchClass, int], ...] = (
    ("input_valid", BranchClass.INVALID_INPUT, 1),
    ("state_valid", BranchClass.INVALID_STATE, 2),
    ("transition_valid", BranchClass.INVALID_TRANSITION, 3),
    ("evidence_valid", BranchClass.INVALID_EVIDENCE, 4),
    ("constraint_valid", BranchClass.INVALID_CONSTRAINT, 5),
    ("destination_valid", BranchClass.INVALID_DESTINATION, 6),
    ("termination_valid", BranchClass.INVALID_TERMINATION, 7),
)


def classify_branch(observation: BranchObservation) -> BranchDecision:
    """Classify an execution branch using fail-closed deterministic precedence."""
    for attribute, branch, precedence in _INVALID_PRECEDENCE:
        if not getattr(observation, attribute):
            return BranchDecision(
                branch=branch,
                valid=False,
                reason=observation.reason or branch.value,
                precedence=precedence,
            )

    if observation.terminal:
        return BranchDecision(
            BranchClass.VALID_TERMINAL,
            True,
            observation.reason or "terminal outcome is explicitly validated",
            8,
        )
    if observation.recovered:
        return BranchDecision(
            BranchClass.VALID_RECOVERY,
            True,
            observation.reason or "execution recovered from a prior failed branch",
            9,
        )
    if observation.progressed:
        return BranchDecision(
            BranchClass.VALID_PROGRESS,
            True,
            observation.reason or "semantic state made valid progress",
            10,
        )
    if observation.no_progress:
        return BranchDecision(
            BranchClass.VALID_NO_PROGRESS,
            True,
            observation.reason or "execution remained valid without semantic progress",
            11,
        )

    # A branch without an explicit valid outcome is rejected rather than
    # guessed into a positive class.
    return BranchDecision(
        BranchClass.INVALID_INPUT,
        False,
        observation.reason or "no explicit branch outcome was declared",
        1,
    )


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    observation: BranchObservation
    expected: BranchClass

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("scenario id must be non-empty")


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    id: str
    expected: BranchClass
    actual: BranchClass
    passed: bool
    decision: BranchDecision


def evaluate_scenario(scenario: Scenario) -> ScenarioResult:
    decision = classify_branch(scenario.observation)
    return ScenarioResult(
        id=scenario.id,
        expected=scenario.expected,
        actual=decision.branch,
        passed=decision.branch is scenario.expected,
        decision=decision,
    )


def run_scenarios(scenarios: tuple[Scenario, ...]) -> tuple[ScenarioResult, ...]:
    return tuple(evaluate_scenario(scenario) for scenario in scenarios)


def assert_scenarios(scenarios: tuple[Scenario, ...]) -> tuple[ScenarioResult, ...]:
    results = run_scenarios(scenarios)
    failures = tuple(result for result in results if not result.passed)
    if failures:
        details = "; ".join(
            f"{result.id}: expected {result.expected.value}, got {result.actual.value}"
            for result in failures
        )
        raise AssertionError(details)
    return results
