from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Optional, Sequence


class ConditionStatus(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class BranchClass(str, Enum):
    VALID_PROGRESS = "VALID_PROGRESS"
    VALID_NO_PROGRESS = "VALID_NO_PROGRESS"
    VALID_RECOVERY = "VALID_RECOVERY"
    VALID_TERMINAL = "VALID_TERMINAL"
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_STATE = "INVALID_STATE"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    INVALID_CONSTRAINT = "INVALID_CONSTRAINT"
    INVALID_DESTINATION = "INVALID_DESTINATION"
    INVALID_TERMINATION = "INVALID_TERMINATION"


class TransitionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNDETERMINED = "undetermined"


class EvaluationDecision(str, Enum):
    CONTINUE = "continue"
    REPLAN = "replan"
    VALIDATE = "validate"
    BLOCKED = "blocked"
    INVALIDATED = "invalidated"
    UNDETERMINED = "undetermined"


class TerminalStatus(str, Enum):
    REACHED = "reached"
    NOT_REACHED = "not_reached"
    BLOCKED = "blocked"
    INVALIDATED = "invalidated"
    UNDETERMINED = "undetermined"


def _required(value: str, name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{name} must be non-empty")
    return value


def _unique(values: Sequence[str], name: str) -> tuple[str, ...]:
    result = tuple(values)
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must not contain duplicates")
    return result


@dataclass(frozen=True, slots=True)
class Provenance:
    source_id: str
    source_type: str
    recorded_at: datetime
    origin: str

    def __post_init__(self) -> None:
        _required(self.source_id, "source_id")
        _required(self.source_type, "source_type")
        _required(self.origin, "origin")


@dataclass(frozen=True, slots=True)
class Intent:
    id: str
    expression: str
    provenance: Provenance
    created_at: datetime
    actor: Optional[str] = None
    requested_outcome: Optional[str] = None
    entities: tuple[str, ...] = ()
    explicit_requirements: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    preferences: tuple[str, ...] = ()
    temporal_conditions: tuple[str, ...] = ()
    authorization_context: Optional[str] = None
    uncertainty: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.expression, "expression")
        _unique(self.entities, "entities")


@dataclass(frozen=True, slots=True)
class UnderstoodIntent:
    source_intent_id: str
    interpretation: str
    outcome: str
    actor: Optional[str] = None
    desired_outcome: Optional[str] = None
    entities: tuple[str, ...] = ()
    explicit_requirements: tuple[str, ...] = ()
    inferred_requirements: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    temporal_meaning: Optional[str] = None
    uncertainty: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.source_intent_id, "source_intent_id")
        _required(self.interpretation, "interpretation")
        _required(self.outcome, "outcome")
        if set(self.inferred_requirements) & set(self.explicit_requirements):
            raise ValueError("inferred and explicit requirements must remain distinct")


@dataclass(frozen=True, slots=True)
class NormalizedIntent:
    source_understood_intent_id: str
    canonical_purpose: str
    requirements: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    actor: Optional[str] = None
    entities: tuple[str, ...] = ()
    preferences: tuple[str, ...] = ()
    temporal_conditions: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()
    unresolved_ambiguities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.source_understood_intent_id, "source_understood_intent_id")
        _required(self.canonical_purpose, "canonical_purpose")


@dataclass(frozen=True, slots=True)
class ContextualizedIntent:
    normalized_intent_id: str
    relevant_context: tuple[str, ...]
    outcome: str
    current_state_id: Optional[str] = None
    historical_facts: tuple[str, ...] = ()
    temporal_context: Optional[str] = None
    actor_context: Optional[str] = None
    environmental_context: tuple[str, ...] = ()
    applicable_rules: tuple[str, ...] = ()
    prior_experience: tuple[str, ...] = ()
    unresolved_context: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Goal:
    id: str
    source_intent_id: str
    desired_outcome: str
    success_meaning: str
    required_semantic_change: tuple[str, ...]
    traceability: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (("id", self.id), ("source_intent_id", self.source_intent_id),
                            ("desired_outcome", self.desired_outcome), ("success_meaning", self.success_meaning)):
            _required(value, name)
        if not self.required_semantic_change:
            raise ValueError("required_semantic_change must not be empty")


@dataclass(frozen=True, slots=True)
class Constraint:
    id: str
    source: str
    predicate: str
    scope: str
    severity: str
    applicability: str
    violation_meaning: str
    active: bool = True

    def __post_init__(self) -> None:
        for name, value in (("id", self.id), ("source", self.source), ("predicate", self.predicate),
                            ("scope", self.scope), ("severity", self.severity),
                            ("applicability", self.applicability), ("violation_meaning", self.violation_meaning)):
            _required(value, name)


@dataclass(frozen=True, slots=True)
class DestinationContract:
    id: str
    goal_id: str
    required_outcome: str
    required_final_state: tuple[str, ...]
    required_evidence: tuple[str, ...]
    constraints: tuple[Constraint, ...]
    completion_conditions: tuple[str, ...]
    failure_conditions: tuple[str, ...]
    validation_rules: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (("id", self.id), ("goal_id", self.goal_id), ("required_outcome", self.required_outcome)):
            _required(value, name)
        if not self.required_final_state or not self.completion_conditions or not self.validation_rules:
            raise ValueError("destination requires final state, completion conditions and validation rules")


@dataclass(frozen=True, slots=True)
class SemanticState:
    id: str
    facts: tuple[str, ...]
    conditions: tuple[tuple[str, ConditionStatus], ...]
    provenance: tuple[Provenance, ...]
    predecessor_state_id: Optional[str] = None
    contradictions: tuple[str, ...] = ()
    temporal_position: Optional[datetime] = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        for condition_id, status in self.conditions:
            _required(condition_id, "condition_id")
            if not isinstance(status, ConditionStatus):
                raise ValueError("condition status must be explicit")


@dataclass(frozen=True, slots=True)
class Transition:
    id: str
    from_state_id: str
    objective: str
    preconditions: tuple[str, ...]
    required_constraints: tuple[str, ...]
    expected_change: tuple[str, ...]
    completion_conditions: tuple[str, ...]
    alternatives: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (("id", self.id), ("from_state_id", self.from_state_id), ("objective", self.objective)):
            _required(value, name)
        if not self.expected_change or not self.completion_conditions:
            raise ValueError("transition requires expected_change and completion_conditions")


@dataclass(frozen=True, slots=True)
class CandidateTrajectory:
    id: str
    origin_state_id: str
    destination_id: str
    transitions: tuple[Transition, ...]
    dependencies: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    validation_points: tuple[str, ...] = ()
    failure_points: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.origin_state_id, "origin_state_id")
        _required(self.destination_id, "destination_id")
        if any(t.objective == "" for t in self.transitions):
            raise ValueError("every transition needs a semantic objective")


@dataclass(frozen=True, slots=True)
class Action:
    id: str
    transition_id: str
    actor: str
    operation: str
    authorization: str
    inputs: tuple[str, ...] = ()
    result: Optional[str] = None
    status: Optional[str] = None

    def __post_init__(self) -> None:
        for name, value in (("id", self.id), ("transition_id", self.transition_id), ("actor", self.actor),
                            ("operation", self.operation), ("authorization", self.authorization)):
            _required(value, name)


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    source_transition_id: str
    observed_fact: str
    temporal_position: datetime
    provenance: Provenance
    supports: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    confidence: Optional[float] = None
    quality: Optional[str] = None

    def __post_init__(self) -> None:
        for name, value in (("id", self.id), ("source_transition_id", self.source_transition_id), ("observed_fact", self.observed_fact)):
            _required(value, name)
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class TransitionResult:
    transition_id: str
    previous_state: SemanticState
    resulting_state: SemanticState
    evidence: tuple[Evidence, ...]
    status: TransitionStatus
    newly_satisfied_conditions: tuple[str, ...] = ()
    unresolved_conditions: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    constraint_violations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.previous_state.id != self.resulting_state.predecessor_state_id:
            raise ValueError("resulting state must point to previous state")


@dataclass(frozen=True, slots=True)
class TransitionEvaluation:
    transition_id: str
    decision: EvaluationDecision
    reason: tuple[str, ...]
    state_assessment: str
    evidence_assessment: str
    constraint_assessment: str
    destination_assessment: str
    next_state_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class DestinationValidation:
    destination_id: str
    required_outcome_satisfied: bool
    final_state_satisfied: bool
    required_evidence_satisfied: bool
    constraints_satisfied: bool
    completion_conditions_satisfied: bool
    failure_conditions_triggered: bool
    unresolved_contradictions: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    outcome: TerminalStatus

    def __post_init__(self) -> None:
        reached = (
            self.required_outcome_satisfied and self.final_state_satisfied
            and self.required_evidence_satisfied and self.constraints_satisfied
            and self.completion_conditions_satisfied and not self.failure_conditions_triggered
            and not self.unresolved_contradictions
        )
        if self.outcome == TerminalStatus.REACHED and not reached:
            raise ValueError("Reached requires every completion predicate")


@dataclass(frozen=True, slots=True)
class TerminalOutcome:
    trajectory_id: str
    destination_id: str
    status: TerminalStatus
    final_state_id: str
    evidence_ids: tuple[str, ...]
    satisfied_conditions: tuple[str, ...]
    unsatisfied_conditions: tuple[str, ...]
    constraint_status: str
    reason: tuple[str, ...]
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class Trajectory:
    id: str
    intent_id: str
    goal_id: str
    destination_id: str
    current_state_id: str
    plan_ids: tuple[str, ...]
    transition_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    status: TerminalStatus | str
    version: int
    provenance: Provenance

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be >= 1")
