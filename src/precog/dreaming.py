from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import Memory, MemoryLifecycle
from .store import InMemoryStore


@dataclass(frozen=True, slots=True)
class DreamReport:
    scanned: int
    deduplicated: int
    stale: int
    archived: int


class Dreamer:
    """Offline derived-state maintenance; Experience is never modified."""

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def run(self, *, now: datetime, stale_after: timedelta = timedelta(days=90)) -> DreamReport:
        memories = self.store.memories(include_archived=True)
        seen: dict[str, str] = {}
        duplicate_ids: set[str] = set()
        stale_ids: set[str] = set()
        for memory in memories:
            key = memory.content.strip().lower()
            if key in seen and memory.lifecycle != MemoryLifecycle.ARCHIVED:
                duplicate_ids.add(memory.id)
            else:
                seen[key] = memory.id
            if memory.created_at < now - stale_after and memory.lifecycle == MemoryLifecycle.ACTIVE:
                stale_ids.add(memory.id)

        archive_ids = duplicate_ids | stale_ids
        for memory in memories:
            if memory.id in archive_ids:
                self.store.put_memory(Memory(
                    memory.id, memory.memory_type, memory.content, memory.source_ids,
                    memory.created_at, memory.valid_from, memory.valid_to,
                    memory.confidence, memory.salience, MemoryLifecycle.ARCHIVED,
                    memory.provenance, memory.schema_version, memory.metadata,
                ))
        return DreamReport(len(memories), len(duplicate_ids), len(stale_ids), len(archive_ids))
