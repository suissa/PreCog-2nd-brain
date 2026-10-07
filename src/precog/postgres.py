from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from .models import Experience, Provenance


class PostgresStore:
    """PostgreSQL persistence adapter for the authoritative Experience boundary.

    The adapter deliberately keeps SQL behind this repository boundary. It does
    not expose a database connection to callers and never treats derived state
    as authoritative.
    """

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def append_experience(self, experience: Experience) -> bool:
        payload = self._json(experience.payload)
        provenance = self._json(experience.provenance)
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO experience (
                    experience_id, trajectory_id, occurred_at, recorded_at,
                    actor, event_type, payload, provenance, intent_id,
                    behavior_id, action, outcome, schema_version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                          %s, %s, %s, %s, %s)
                ON CONFLICT (experience_id) DO NOTHING
                RETURNING experience_id
                """,
                (
                    experience.id, experience.trajectory_id, experience.occurred_at,
                    experience.recorded_at, experience.actor, experience.event_type,
                    payload, provenance, experience.intent_id, experience.behavior_id,
                    experience.action, experience.outcome, experience.schema_version,
                ),
            )
            inserted = cursor.fetchone()
        if inserted is not None:
            self._connection.commit()
            return True

        existing = self.get_experience(experience.id)
        if existing != experience:
            raise ValueError("experience id already exists with different content")
        return False

    def get_experience(self, experience_id: str) -> Experience | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT experience_id, trajectory_id, occurred_at, recorded_at,
                       actor, event_type, payload, provenance, schema_version,
                       intent_id, behavior_id, action, outcome
                FROM experience
                WHERE experience_id = %s
                """,
                (experience_id,),
            )
            row = cursor.fetchone()
        return self._experience_from_row(row) if row else None

    def experiences(self, trajectory_id: str | None = None) -> tuple[Experience, ...]:
        query = """
            SELECT experience_id, trajectory_id, occurred_at, recorded_at,
                   actor, event_type, payload, provenance, schema_version,
                   intent_id, behavior_id, action, outcome
            FROM experience
        """
        params: Sequence[Any] = ()
        if trajectory_id is not None:
            query += " WHERE trajectory_id = %s"
            params = (trajectory_id,)
        query += " ORDER BY occurred_at, experience_id"

        with self._connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return tuple(self._experience_from_row(row) for row in rows)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)

    @staticmethod
    def _experience_from_row(row: Sequence[Any]) -> Experience:
        payload = row[6]
        provenance = row[7]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(provenance, str):
            provenance = json.loads(provenance)
        p = Provenance(
            tuple(provenance["source_ids"]),
            provenance["derivation"],
            provenance.get("schema_version", 1),
        )
        return Experience(
            id=row[0],
            trajectory_id=row[1],
            occurred_at=row[2],
            recorded_at=row[3],
            actor=row[4],
            event_type=row[5],
            payload=payload,
            provenance=p,
            schema_version=row[8],
            intent_id=row[9],
            behavior_id=row[10],
            action=row[11],
            outcome=row[12],
        )
