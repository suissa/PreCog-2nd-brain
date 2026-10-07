from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .models import Experience, Knowledge, Memory, MemoryLifecycle, Relation, RelationType, Trajectory, Provenance


class InMemoryStore:
    """Deterministic reference store for the canonical source-of-truth boundary."""

    def __init__(self) -> None:
        self._experiences: dict[str, Experience] = {}
        self._trajectories: dict[str, Trajectory] = {}
        self._memories: dict[str, Memory] = {}
        self._memory_history: dict[str, tuple[Memory, ...]] = {}
        self._knowledge: dict[str, Knowledge] = {}
        self._relations: dict[str, Relation] = {}

    def append_experience(self, experience: Experience) -> bool:
        existing = self._experiences.get(experience.id)
        if existing is not None:
            if existing != replace(experience, recorded_at=existing.recorded_at):
                raise ValueError("experience id already exists with different content")
            return False
        stored = replace(experience, recorded_at=datetime.now(timezone.utc))
        self._experiences[experience.id] = stored
        return True

    def experiences(self, trajectory_id: str | None = None) -> tuple[Experience, ...]:
        values = self._experiences.values()
        if trajectory_id is not None:
            return tuple(sorted((e for e in values if e.trajectory_id == trajectory_id), key=lambda e: (e.occurred_at, e.id)))
        return tuple(sorted(values, key=lambda e: (e.occurred_at, e.id)))

    def upsert_trajectory(self, trajectory: Trajectory) -> None:
        if any(i not in self._experiences for i in trajectory.experience_ids):
            raise ValueError("trajectory references unknown experience")
        self._trajectories[trajectory.id] = trajectory

    def trajectory(self, trajectory_id: str) -> Trajectory:
        return self._trajectories[trajectory_id]

    def put_memory(self, memory: Memory) -> None:
        if any(not self._exists(i) for i in memory.source_ids):
            raise ValueError("memory provenance references unknown source")
        existing = self._memories.get(memory.id)
        if existing is not None:
            if memory.version != existing.version + 1:
                raise ValueError("memory version must advance exactly by one")
            if not existing.lifecycle.can_transition_to(memory.lifecycle):
                raise ValueError(
                    f"illegal memory lifecycle transition: "
                    f"{existing.lifecycle.value} -> {memory.lifecycle.value}"
                )
            history = self._memory_history.get(memory.id, (existing,))
            self._memory_history[memory.id] = history + (memory,)
        else:
            if memory.version != 1:
                raise ValueError("new memory must start at version 1")
            self._memory_history[memory.id] = (memory,)
        self._memories[memory.id] = memory

    def memory_history(self, memory_id: str) -> tuple[Memory, ...]:
        return self._memory_history[memory_id]

    def memories(self, include_archived: bool = False) -> tuple[Memory, ...]:
        if include_archived:
            return tuple(self._memories.values())
        return tuple(m for m in self._memories.values() if m.lifecycle != MemoryLifecycle.ARCHIVED)

    def memories_at(self, at: datetime) -> tuple[Memory, ...]:
        return tuple(
            m for m in self._memories.values()
            if m.is_valid_at(at) and m.lifecycle != MemoryLifecycle.ARCHIVED
        )

    def current_memories(self) -> tuple[Memory, ...]:
        return tuple(m for m in self._memories.values() if m.is_current)

    def historical_memories(self, at: datetime) -> tuple[Memory, ...]:
        return tuple(
            m for m in self._memories.values()
            if m.valid_to is not None and m.valid_to <= at
        )

    def record_supersession(
        self,
        old_memory_id: str,
        new_memory_id: str,
        *,
        at: datetime,
        provenance: "Provenance",
        confidence: float = 1.0,
    ) -> Relation:
        old = self._memories[old_memory_id]
        new = self._memories[new_memory_id]
        if at < old.created_at:
            raise ValueError("supersession cannot precede old memory creation")
        if new.valid_from is not None and new.valid_from < at:
            raise ValueError("new memory is valid before supersession time")
        closed = replace(old, valid_to=at)
        self._memories[old.id] = closed
        self._memory_history[old.id] = self._memory_history[old.id] + (closed,)
        relation = Relation(
            f"supersedes:{old.id}:{new.id}",
            old.id,
            new.id,
            RelationType.SUPERSEDES,
            confidence,
            at,
            valid_from=at,
            provenance=provenance,
        )
        self.put_relation(relation)
        return relation

    def record_contradiction(
        self,
        left_memory_id: str,
        right_memory_id: str,
        *,
        at: datetime,
        provenance: "Provenance",
        confidence: float,
    ) -> Relation:
        if left_memory_id == right_memory_id:
            raise ValueError("contradiction endpoints must differ")
        self._memories[left_memory_id]
        self._memories[right_memory_id]
        relation = Relation(
            f"contradicts:{left_memory_id}:{right_memory_id}",
            left_memory_id,
            right_memory_id,
            RelationType.CONTRADICTS,
            confidence,
            at,
            valid_from=at,
            provenance=provenance,
        )
        self.put_relation(relation)
        return relation

    def contradictions(self, memory_id: str) -> tuple[Relation, ...]:
        return tuple(
            r for r in self._relations.values()
            if r.relation_type is RelationType.CONTRADICTS
            and (r.source_id == memory_id or r.target_id == memory_id)
        )

    def put_knowledge(self, knowledge: Knowledge) -> None:
        if any(not self._exists(i) for i in knowledge.evidence_ids):
            raise ValueError("knowledge evidence references unknown object")
        self._knowledge[knowledge.id] = knowledge

    def knowledge(self) -> tuple[Knowledge, ...]:
        return tuple(self._knowledge.values())

    def put_relation(self, relation: Relation) -> None:
        if not self._exists(relation.source_id) or not self._exists(relation.target_id):
            raise ValueError("relation endpoints must exist")
        self._relations[relation.id] = relation

    def relations(self) -> tuple[Relation, ...]:
        return tuple(self._relations.values())

    def _exists(self, object_id: str) -> bool:
        return object_id in self._experiences or object_id in self._memories or object_id in self._knowledge

    def rebuildable_snapshot(self) -> dict[str, int]:
        return {
            "experiences": len(self._experiences),
            "trajectories": len(self._trajectories),
            "memories": len(self._memories),
            "knowledge": len(self._knowledge),
            "relations": len(self._relations),
        }
