from __future__ import annotations

from datetime import datetime
from .models import Relation, RelationType
from .store import InMemoryStore


@dataclass(frozen=True, slots=True)
class RelationPath:
    nodes: tuple[str, ...]
    edges: tuple[Relation, ...]


from dataclasses import dataclass


class RelationGraph:
    """Deterministic bounded traversal over typed, provenance-bearing relations."""

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def outgoing(self, source_id: str, *, at: datetime | None = None) -> tuple[Relation, ...]:
        return tuple(sorted(
            (r for r in self.store.relations() if r.source_id == source_id and self._valid(r, at)),
            key=lambda r: (r.relation_type.value, r.target_id, r.id),
        ))

    def contradictions(self, object_id: str, *, at: datetime | None = None) -> tuple[Relation, ...]:
        return tuple(sorted(
            (r for r in self.store.relations() if r.relation_type is RelationType.CONTRADICTS
             and (r.source_id == object_id or r.target_id == object_id) and self._valid(r, at)),
            key=lambda r: r.id,
        ))

    def traverse(self, start_id: str, *, max_depth: int, relation_types: tuple[RelationType, ...] | None = None, at: datetime | None = None) -> tuple[RelationPath, ...]:
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        if not self.store._exists(start_id):
            raise ValueError("unknown traversal start node")
        allowed = set(relation_types) if relation_types is not None else set(RelationType)
        edges = self.store.relations()
        results: list[RelationPath] = []
        frontier: list[RelationPath] = [RelationPath((start_id,), ())]
        while frontier:
            path = frontier.pop(0)
            if path.edges:
                results.append(path)
            if len(path.edges) >= max_depth:
                continue
            tail = path.nodes[-1]
            for edge in edges:
                if edge.source_id != tail or edge.relation_type not in allowed or not self._valid(edge, at):
                    continue
                if edge.target_id in path.nodes and edge.relation_type in {
                    RelationType.DERIVED_FROM, RelationType.CAUSED_BY, RelationType.GENERALIZES,
                    RelationType.SPECIALIZES, RelationType.SUPERSEDES, RelationType.FOLLOWS,
                }:
                    continue
                frontier.append(RelationPath(path.nodes + (edge.target_id,), path.edges + (edge,)))
        return tuple(results)

    def project(self) -> tuple[tuple[str, str, str], ...]:
        return tuple((r.source_id, r.relation_type.value, r.target_id) for r in self.store.relations())

    @staticmethod
    def _valid(relation: Relation, at: datetime | None) -> bool:
        return at is None or ((relation.valid_from is None or relation.valid_from <= at) and (relation.valid_to is None or at <= relation.valid_to))
