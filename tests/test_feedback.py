from datetime import datetime, timezone

import pytest

from precog.feedback import ExecutionFeedbackRecorder, ExecutionResult
from precog.store import InMemoryStore

NOW = datetime(2026, 10, 13, 1, 0, tzinfo=timezone.utc)


def result(**overrides: object) -> ExecutionResult:
    values: dict[str, object] = {
        "event_id": "runtime-event-123",
        "trajectory_id": "trajectory-1",
        "actor": "sales-agent",
        "behavior_id": "create-order",
        "action": "persist-order",
        "outcome": "succeeded",
        "occurred_at": NOW,
        "recorded_at": NOW,
        "payload": {"order_id": "order-42"},
        "intent_id": "create-order-intent",
        "source_ids": ("trace-123", "memory-7"),
    }
    values.update(overrides)
    return ExecutionResult(**values)  # type: ignore[arg-type]


def test_runtime_outcome_becomes_canonical_experience() -> None:
    store = InMemoryStore()
    recorded = ExecutionFeedbackRecorder(store).record(result())

    assert recorded.inserted is True
    assert recorded.experience.event_type == "execution_result"
    assert recorded.experience.trajectory_id == "trajectory-1"
    assert recorded.experience.behavior_id == "create-order"
    assert recorded.experience.action == "persist-order"
    assert recorded.experience.outcome == "succeeded"
    assert recorded.experience.intent_id == "create-order-intent"
    assert recorded.experience.provenance.source_ids == ("trace-123", "memory-7")
    assert store.experiences("trajectory-1") == (recorded.experience,)


def test_replaying_same_runtime_event_is_idempotent() -> None:
    store = InMemoryStore()
    recorder = ExecutionFeedbackRecorder(store)

    first = recorder.record(result())
    replay = recorder.record(result())

    assert first.inserted is True
    assert replay.inserted is False
    assert replay.experience.id == first.experience.id
    assert len(store.experiences()) == 1


def test_reusing_event_id_for_different_outcome_is_rejected() -> None:
    store = InMemoryStore()
    recorder = ExecutionFeedbackRecorder(store)
    recorder.record(result())

    with pytest.raises(ValueError, match="different content"):
        recorder.record(result(outcome="failed"))


def test_execution_result_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        result(occurred_at=datetime(2026, 10, 13, 1, 0))
