from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any

from .models import (
    Experience, Knowledge, Memory, MemoryLifecycle, MemoryType,
    Provenance, Relation, RelationType, Trajectory,
)


class PostgresStore:
    """PostgreSQL persistence adapter for canonical and derived PreCog state."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def append_experience(self, experience: Experience) -> bool:
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO experience (
                        experience_id, trajectory_id, occurred_at, recorded_at,
                        actor, event_type, payload, provenance, intent_id,
                        behavior_id, action, outcome, schema_version
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)
                    ON CONFLICT (experience_id) DO NOTHING RETURNING experience_id""",
                    (experience.id, experience.trajectory_id, experience.occurred_at,
                     self._recorded_at_sql(), experience.actor, experience.event_type,
                     self._json(experience.payload), self._json(experience.provenance),
                     experience.intent_id, experience.behavior_id, experience.action,
                     experience.outcome, experience.schema_version),
                )
                inserted = cursor.fetchone()
            if inserted is not None:
                self._connection.commit()
                return True
            existing = self.get_experience(experience.id)
            if existing != replace(experience, recorded_at=existing.recorded_at):
                raise ValueError("experience id already exists with different content")
            return False
        except Exception:
            self._connection.rollback()
            raise

    def get_experience(self, experience_id: str) -> Experience | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT experience_id, trajectory_id, occurred_at, recorded_at,
                    actor, event_type, payload, provenance, schema_version,
                    intent_id, behavior_id, action, outcome
                    FROM experience WHERE experience_id = %s""", (experience_id,))
            row = cursor.fetchone()
        return self._experience_from_row(row) if row else None

    def experiences(self, trajectory_id: str | None = None) -> tuple[Experience, ...]:
        query = """SELECT experience_id, trajectory_id, occurred_at, recorded_at,
            actor, event_type, payload, provenance, schema_version,
            intent_id, behavior_id, action, outcome FROM experience"""
        params: Sequence[Any] = ()
        if trajectory_id is not None:
            query += " WHERE trajectory_id = %s"
            params = (trajectory_id,)
        query += " ORDER BY occurred_at, experience_id"
        with self._connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return tuple(self._experience_from_row(row) for row in rows)

    def upsert_trajectory(self, trajectory: Trajectory) -> None:
        self._require_experiences(trajectory.experience_ids)
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO trajectory
                    (trajectory_id, started_at, ended_at, status, experience_ids, schema_version)
                    VALUES (%s,%s,%s,%s,%s::jsonb,%s)
                    ON CONFLICT (trajectory_id) DO UPDATE SET
                    started_at=EXCLUDED.started_at, ended_at=EXCLUDED.ended_at,
                    status=EXCLUDED.status, experience_ids=EXCLUDED.experience_ids,
                    schema_version=EXCLUDED.schema_version""",
                (trajectory.id, trajectory.started_at, trajectory.ended_at, trajectory.status,
                 self._json(trajectory.experience_ids), trajectory.schema_version),
            )
        self._connection.commit()

    def trajectory(self, trajectory_id: str) -> Trajectory:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT trajectory_id, started_at, ended_at, status,
                    experience_ids, schema_version FROM trajectory
                    WHERE trajectory_id = %s""", (trajectory_id,))
            row = cursor.fetchone()
        if row is None:
            raise KeyError(trajectory_id)
        ids = row[4] if not isinstance(row[4], str) else json.loads(row[4])
        return Trajectory(row[0], tuple(ids), row[1], row[2], row[3], row[5])

    def put_memory(self, memory: Memory) -> None:
        self._require_sources(memory.source_ids)
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO memory
                    (memory_id,memory_type,content,source_ids,created_at,valid_from,valid_to,
                     confidence,salience,lifecycle,provenance,metadata,schema_version)
                    VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                    ON CONFLICT (memory_id) DO UPDATE SET
                    memory_type=EXCLUDED.memory_type, content=EXCLUDED.content,
                    source_ids=EXCLUDED.source_ids, created_at=EXCLUDED.created_at,
                    valid_from=EXCLUDED.valid_from, valid_to=EXCLUDED.valid_to,
                    confidence=EXCLUDED.confidence, salience=EXCLUDED.salience,
                    lifecycle=EXCLUDED.lifecycle, provenance=EXCLUDED.provenance,
                    metadata=EXCLUDED.metadata, schema_version=EXCLUDED.schema_version""",
                (memory.id, memory.memory_type.value, memory.content,
                 self._json(memory.source_ids), memory.created_at, memory.valid_from,
                 memory.valid_to, memory.confidence, memory.salience, memory.lifecycle.value,
                 self._json(memory.provenance), self._json(memory.metadata), memory.schema_version),
            )
        self._connection.commit()

    def memories(self, include_archived: bool = False) -> tuple[Memory, ...]:
        query = """SELECT memory_id,memory_type,content,source_ids,created_at,valid_from,valid_to,
                   confidence,salience,lifecycle,provenance,metadata,schema_version FROM memory"""
        if not include_archived:
            query += " WHERE lifecycle <> %s"
            params: Sequence[Any] = (MemoryLifecycle.ARCHIVED.value,)
        else:
            params = ()
        query += " ORDER BY created_at, memory_id"
        with self._connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return tuple(self._memory_from_row(r) for r in rows)

    def put_knowledge(self, knowledge: Knowledge) -> None:
        self._require_sources(knowledge.evidence_ids)
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO knowledge
                    (knowledge_id,statement,scope,evidence_ids,confidence,status,version,
                     created_at,valid_from,valid_to,provenance)
                    VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT (knowledge_id) DO UPDATE SET
                    statement=EXCLUDED.statement, scope=EXCLUDED.scope,
                    evidence_ids=EXCLUDED.evidence_ids, confidence=EXCLUDED.confidence,
                    status=EXCLUDED.status, version=EXCLUDED.version,
                    created_at=EXCLUDED.created_at, valid_from=EXCLUDED.valid_from,
                    valid_to=EXCLUDED.valid_to, provenance=EXCLUDED.provenance""",
                (knowledge.id, knowledge.statement, knowledge.scope,
                 self._json(knowledge.evidence_ids), knowledge.confidence, knowledge.status,
                 knowledge.version, knowledge.created_at, knowledge.valid_from,
                 knowledge.valid_to, self._json(knowledge.provenance)),
            )
        self._connection.commit()

    def knowledge(self) -> tuple[Knowledge, ...]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT knowledge_id,statement,scope,evidence_ids,confidence,status,version,
                    created_at,valid_from,valid_to,provenance FROM knowledge
                    ORDER BY created_at, knowledge_id""", ())
            rows = cursor.fetchall()
        return tuple(self._knowledge_from_row(r) for r in rows)

    def put_relation(self, relation: Relation) -> None:
        self._require_sources((relation.source_id, relation.target_id))
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO relation
                    (relation_id,source_id,target_id,relation_type,confidence,created_at,
                     valid_from,valid_to,provenance)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT (relation_id) DO UPDATE SET
                    source_id=EXCLUDED.source_id,target_id=EXCLUDED.target_id,
                    relation_type=EXCLUDED.relation_type,confidence=EXCLUDED.confidence,
                    created_at=EXCLUDED.created_at,valid_from=EXCLUDED.valid_from,
                    valid_to=EXCLUDED.valid_to,provenance=EXCLUDED.provenance""",
                (relation.id, relation.source_id, relation.target_id, relation.relation_type.value,
                 relation.confidence, relation.created_at, relation.valid_from, relation.valid_to,
                 self._json(relation.provenance)),
            )
        self._connection.commit()

    def relations(self) -> tuple[Relation, ...]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT relation_id,source_id,target_id,relation_type,confidence,created_at,
                    valid_from,valid_to,provenance FROM relation
                    ORDER BY created_at, relation_id""", ())
            rows = cursor.fetchall()
        return tuple(self._relation_from_row(r) for r in rows)

    def _require_experiences(self, ids: Sequence[str]) -> None:
        if not ids:
            return
        placeholders = ",".join(["%s"] * len(ids))
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"SELECT experience_id FROM experience WHERE experience_id IN ({placeholders})",
                tuple(ids),
            )
            found = {r[0] for r in cursor.fetchall()}
        missing = set(ids) - found
        if missing:
            raise ValueError("trajectory references unknown experience")

    def _require_sources(self, ids: Sequence[str]) -> None:
        if not ids:
            raise ValueError("provenance requires source ids")
        placeholders = ",".join(["%s"] * len(ids))
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""SELECT object_id FROM (
                    SELECT experience_id AS object_id FROM experience
                    UNION ALL SELECT memory_id FROM memory
                    UNION ALL SELECT knowledge_id FROM knowledge
                ) sources WHERE object_id IN ({placeholders})""", tuple(ids))
            found = {r[0] for r in cursor.fetchall()}
        if set(ids) - found:
            raise ValueError("provenance references unknown source")

    @staticmethod
    def _recorded_at_sql() -> Any:
        return datetime.now(timezone.utc)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)

    @staticmethod
    def _decode(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @classmethod
    def _provenance(cls, value: Any) -> Provenance:
        data = cls._decode(value)
        return Provenance(tuple(data["source_ids"]), data["derivation"], data.get("schema_version", 1))

    @classmethod
    def _experience_from_row(cls, row: Sequence[Any]) -> Experience:
        return Experience(row[0], row[1], row[2], row[3], row[4], row[5], cls._decode(row[6]),
                           cls._provenance(row[7]), row[8], row[9], row[10], row[11], row[12])

    @classmethod
    def _memory_from_row(cls, row: Sequence[Any]) -> Memory:
        return Memory(row[0], MemoryType(row[1]), row[2], tuple(cls._decode(row[3])),
                      row[4], row[5], row[6], row[7], row[8], MemoryLifecycle(row[9]),
                      cls._provenance(row[10]), row[12], cls._decode(row[11]))

    @classmethod
    def _knowledge_from_row(cls, row: Sequence[Any]) -> Knowledge:
        return Knowledge(row[0], row[1], row[2], tuple(cls._decode(row[3])), row[4], row[5],
                         row[6], row[7], row[8], row[9], cls._provenance(row[10]))

    @classmethod
    def _relation_from_row(cls, row: Sequence[Any]) -> Relation:
        return Relation(row[0], row[1], row[2], RelationType(row[3]), row[4], row[5], row[6],
                        row[7], cls._provenance(row[8]))
