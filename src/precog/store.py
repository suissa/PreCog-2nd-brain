from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .models import Experience, Knowledge, Memory, MemoryLifecycle, Relation, Trajectory


class InMemoryStore:
    """Deterministic reference store for the canonical source-of-truth boundary."""

    def __init__(self) -> None:
        self._experiences: dict[str, Experience] = {}
        self._trajectories: dict[str, Trajectory] = {}
        self._memories: dict[str, Memory] = {}
        self._knowledge: dict[str, Knowledge] = {}
        self._relations: dict[str, Relation] = {}

    def append_experience(self, experience: Experience) -> bool:
        existing = self._experiences.get(experience.id)
        if existing is not None:
            if existing != experience:
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
        self._memories[memory.id] = memory

    def memories(self, include_archived: bool = False) -> tuple[Memory, ...]:
        if include_archived:
            return tuple(self._memories.values())
        return tuple(m for m in self._memories.values() if m.lifecycle != MemoryLifecycle.ARCHIVED)

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
