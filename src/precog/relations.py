from __future__ import annotations

from datetime import datetime

from .models import Relation, RelationType
from .store import InMemoryStore


class RelationGraph:
    """Deterministic temporal graph projection over canonical relations."""

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def outgoing(self, source_id: str, *, at: datetime | None = None) -> tuple[Relation, ...]:
        values = tuple(r for r in self.store.relations() if r.source_id == source_id)
        if at is not None:
            values = tuple(
                r for r in values
                if (r.valid_from is None or r.valid_from <= at)
                and (r.valid_to is None or at <= r.valid_to)
            )
        return tuple(sorted(values, key=lambda r: (r.relation_type.value, r.target_id, r.id)))

    def contradictions(self, object_id: str, *, at: datetime | None = None) -> tuple[Relation, ...]:
        return tuple(
            r for r in self.store.relations()
            if r.relation_type is RelationType.CONTRADICTS
            and (r.source_id == object_id or r.target_id == object_id)
            and (at is None or (r.valid_from is None or r.valid_from <= at))
            and (at is None or (r.valid_to is None or at <= r.valid_to))
        )

    def project(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(
            (r.source_id, r.relation_type.value, r.target_id)
            for r in sorted(self.store.relations(), key=lambda x: x.id)
        )
