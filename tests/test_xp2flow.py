import pytest

from precog.xp2flow import FlowStep, FlowValidationError, XP2Flow, validate_flow


def flow(*steps: FlowStep) -> XP2Flow:
    return XP2Flow("test.flow", 1, tuple(steps))


def test_validator_returns_deterministic_topological_order() -> None:
    definition = flow(
        FlowStep("finish", "evaluate", depends_on=("capture", "retrieve")),
        FlowStep("retrieve", "retrieve", depends_on=("capture",)),
        FlowStep("capture", "capture"),
    )
    assert validate_flow(definition) == ("capture", "retrieve", "finish")


def test_independent_steps_can_be_reordered() -> None:
    first = flow(FlowStep("alpha", "read_a"), FlowStep("beta", "read_b"))
    second = flow(FlowStep("beta", "read_b"), FlowStep("alpha", "read_a"))
    assert validate_flow(first) == validate_flow(second)


def test_duplicate_step_ids_are_rejected() -> None:
    with pytest.raises(FlowValidationError, match="duplicate step_id"):
        validate_flow(flow(FlowStep("same", "read"), FlowStep("same", "write")))


def test_missing_dependency_is_rejected() -> None:
    with pytest.raises(FlowValidationError, match="unresolved dependencies"):
        validate_flow(flow(FlowStep("step", "read", depends_on=("missing",))))


def test_dependency_cycle_is_rejected() -> None:
    with pytest.raises(FlowValidationError, match="cycle"):
        validate_flow(
            flow(
                FlowStep("a", "read", depends_on=("b",)),
                FlowStep("b", "write", depends_on=("a",)),
            )
        )


def test_conflicting_unordered_effects_are_rejected() -> None:
    with pytest.raises(FlowValidationError, match="conflict on: knowledge"):
        validate_flow(
            flow(
                FlowStep("read", "read", reads=("knowledge",)),
                FlowStep("write", "write", writes=("knowledge",)),
            )
        )


def test_conflicting_effects_are_allowed_when_ordered() -> None:
    definition = flow(
        FlowStep("write", "write", writes=("knowledge",)),
        FlowStep("read", "read", depends_on=("write",), reads=("knowledge",)),
    )
    assert validate_flow(definition) == ("write", "read")


def test_registered_kind_allowlist_rejects_unknown_steps() -> None:
    with pytest.raises(FlowValidationError, match="unregistered step kind"):
        validate_flow(flow(FlowStep("unknown", "model_magic")), registered_kinds=frozenset({"capture"}))


def test_empty_flow_is_rejected() -> None:
    with pytest.raises(FlowValidationError, match="at least one step"):
        validate_flow(XP2Flow("empty", 1, ()))
