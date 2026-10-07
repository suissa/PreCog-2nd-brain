from datetime import datetime, timedelta, timezone

import pytest

from precog.contract import DataClass, FieldPolicy, PrivacyPolicy, validate_migration_version
from precog.models import Experience, Memory, MemoryLifecycle, MemoryType, Provenance
from precog.store import InMemoryStore
from precog.trajectory import reconstruct_trajectory
from precog.retrieval import HybridRetriever
from precog.consolidation import Consolidator
from precog.dreaming import Dreamer
from precog.prediction import BehaviorPredictor
from precog.models import Behavior

NOW = datetime.now(timezone.utc)


def experience(i: str, behavior: str | None = None, outcome: str | None = None) -> Experience:
    return Experience(
        i, "t1", NOW + timedelta(seconds=int(i[1:])), NOW,
        "actor", "action", {"value": i},
        Provenance((i,), "capture"), behavior_id=behavior, outcome=outcome,
    )


def test_experience_is_append_only_and_idempotent() -> None:
    store = InMemoryStore()
    e = experience("e1")
    assert store.append_experience(e) is True
    assert store.append_experience(e) is False
    changed = experience("e1", outcome="changed")
    with pytest.raises(ValueError):
        store.append_experience(changed)


def test_trajectory_reconstruction_is_temporal() -> None:
    store = InMemoryStore()
    e2, e1 = experience("e2"), experience("e1")
    store.append_experience(e2)
    store.append_experience(e1)
    trajectory = reconstruct_trajectory("t1", store.experiences("t1"))
    assert trajectory.experience_ids == ("e1", "e2")


def test_memory_provenance_and_retrieval() -> None:
    store = InMemoryStore()
    e = experience("e1")
    store.append_experience(e)
    m = Memory("m1", MemoryType.SEMANTIC, "customer prefers morning", ("e1",), NOW,
               confidence=0.9, salience=0.8, lifecycle=MemoryLifecycle.ACTIVE,
               provenance=Provenance(("e1",), "consolidation"))
    store.put_memory(m)
    result = HybridRetriever(store).search("customer morning", now=NOW)
    assert result and result[0].object_id == "m1"


def test_relation_endpoints_are_valid() -> None:
    from precog.models import Relation, RelationType
    store = InMemoryStore()
    e = experience("e1")
    store.append_experience(e)
    m = Memory("m1", MemoryType.SEMANTIC, "fact", ("e1",), NOW,
               provenance=Provenance(("e1",), "consolidation"))
    store.put_memory(m)
    store.put_relation(Relation("r1", "e1", "m1", RelationType.DERIVED_FROM, 1.0, NOW,
                                provenance=Provenance(("e1",), "relation")))
    assert len(store.relations()) == 1


def test_consolidation_requires_validation_before_active() -> None:
    store = InMemoryStore()
    store.append_experience(experience("e1", outcome="ok"))
    store.append_experience(experience("e2", outcome="ok"))
    proposal = Consolidator(store).propose(store.experiences("t1"))
    assert Consolidator(store).validate(proposal)
    memory = Consolidator(store).materialize_memory(proposal, now=NOW)
    assert memory.lifecycle is MemoryLifecycle.ACTIVE


def test_contradiction_stays_candidate() -> None:
    store = InMemoryStore()
    store.append_experience(experience("e1", outcome="ok"))
    store.append_experience(experience("e2", outcome="failed"))
    proposal = Consolidator(store).propose(store.experiences("t1"))
    memory = Consolidator(store).materialize_memory(proposal, now=NOW)
    assert memory.lifecycle is MemoryLifecycle.CANDIDATE


def test_dreaming_archives_stale_memory_without_touching_experience() -> None:
    store = InMemoryStore()
    e = experience("e1")
    store.append_experience(e)
    old = Memory("m1", MemoryType.SEMANTIC, "old fact", ("e1",), NOW - timedelta(days=100),
                   confidence=1.0, salience=0.5, lifecycle=MemoryLifecycle.ACTIVE,
                   provenance=Provenance(("e1",), "consolidation"))
    store.put_memory(old)
    report = Dreamer(store).run(now=NOW, stale_after=timedelta(days=90))
    assert report.archived == 1
    assert store.experiences() == (store.experiences()[0],)
    assert not store.memories()


def test_behavior_prediction_is_not_authorization() -> None:
    experiences = (experience("e1", "b1"), experience("e2", "b1"), experience("e3", "b2"))
    behaviors = (
        Behavior("b1", "book", (), (), ("book",), "booked"),
        Behavior("b2", "cancel", (), (), ("cancel",), "cancelled"),
    )
    predictions = BehaviorPredictor().predict(experiences, behaviors)
    assert predictions[0].behavior_id == "b1"
    assert predictions[0].probability > predictions[1].probability


def test_privacy_policy_redacts_sensitive_fields() -> None:
    policy = PrivacyPolicy((
        FieldPolicy("email", DataClass.PII, embed=False, trace=False),
        FieldPolicy("secret", DataClass.SECRET, embed=False, trace=False),
        FieldPolicy("topic", DataClass.PUBLIC, embed=True, trace=True),
    ))
    payload = {"email": "x", "secret": "y", "topic": "book"}
    assert policy.sanitize_for_embedding(payload) == {"topic": "book"}
    assert policy.sanitize_for_trace(payload) == {"topic": "book"}


def test_migration_is_monotonic() -> None:
    validate_migration_version(2, 1)
    with pytest.raises(ValueError):
        validate_migration_version(4, 1)


def test_experience_recorded_at_is_assigned_by_store() -> None:
    store = InMemoryStore()
    e = experience("e9")
    store.append_experience(e)
    stored = store.experiences()[0]
    assert stored.occurred_at == e.occurred_at
    assert stored.recorded_at >= e.recorded_at


def test_memory_lifecycle_rejects_illegal_transition_and_retains_history() -> None:
    store = InMemoryStore()
    store.append_experience(experience("e10"))
    memory = Memory(
        "m10", MemoryType.SEMANTIC, "fact", ("e10",), NOW,
        lifecycle=MemoryLifecycle.CANDIDATE,
        provenance=Provenance(("e10",), "consolidation"),
    )
    store.put_memory(memory)
    validated = memory.transition_to(MemoryLifecycle.VALIDATED)
    store.put_memory(validated)
    active = validated.transition_to(MemoryLifecycle.ACTIVE)
    store.put_memory(active)
    assert tuple(m.version for m in store.memory_history("m10")) == (1, 2, 3)
    assert store.memories() == (active,)
    with pytest.raises(ValueError, match="illegal memory lifecycle transition"):
        store.put_memory(active.transition_to(MemoryLifecycle.ARCHIVED).transition_to(MemoryLifecycle.ACTIVE))
