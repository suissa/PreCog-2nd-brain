from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Any, Mapping


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    ENTITY = "entity"
    PROCEDURAL = "procedural"
    OBSERVATIONAL = "observational"


class MemoryLifecycle(str, Enum):
    CAPTURED = "captured"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    ACTIVE = "active"
    DORMANT = "dormant"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class RelationType(str, Enum):
    DERIVED_FROM = "derived_from"
    CAUSED_BY = "caused_by"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    GENERALIZES = "generalizes"
    SPECIALIZES = "specializes"
    SUPERSEDES = "supersedes"
    FOLLOWS = "follows"
    RELATED_TO = "related_to"
    APPLIES_TO = "applies_to"
    PREDICTS = "predicts"


@dataclass(frozen=True, slots=True)
class Provenance:
    source_ids: tuple[str, ...]
    derivation: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.source_ids or not self.derivation:
            raise ValueError("provenance requires source_ids and derivation")
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1")


@dataclass(frozen=True, slots=True)
class Experience:
    id: str
    trajectory_id: str
    occurred_at: datetime
    recorded_at: datetime
    actor: str
    event_type: str
    payload: Mapping[str, Any]
    provenance: Provenance
    schema_version: int = 1
    intent_id: str | None = None
    behavior_id: str | None = None
    action: str | None = None
    outcome: str | None = None

    def __post_init__(self) -> None:
        for value, name in ((self.id, "id"), (self.trajectory_id, "trajectory_id"),
                            (self.actor, "actor"), (self.event_type, "event_type")):
            if not value:
                raise ValueError(f"{name} must be non-empty")
        if self.recorded_at.tzinfo is None or self.occurred_at.tzinfo is None:
            raise ValueError("experience timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Trajectory:
    id: str
    experience_ids: tuple[str, ...]
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "active"
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class Memory:
    id: str
    memory_type: MemoryType
    content: str
    source_ids: tuple[str, ...]
    created_at: datetime
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = 1.0
    salience: float = 0.5
    lifecycle: MemoryLifecycle = MemoryLifecycle.CANDIDATE
    provenance: Provenance = field(default_factory=lambda: Provenance(("unknown",), "unknown"))
    schema_version: int = 1
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.content or not self.source_ids:
            raise ValueError("memory requires id, content and source_ids")
        if not 0 <= self.confidence <= 1 or not 0 <= self.salience <= 1:
            raise ValueError("confidence and salience must be between 0 and 1")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("invalid memory temporal interval")


@dataclass(frozen=True, slots=True)
class Relation:
    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    confidence: float
    created_at: datetime
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    provenance: Provenance = field(default_factory=lambda: Provenance(("unknown",), "unknown"))

    def __post_init__(self) -> None:
        if self.source_id == self.target_id:
            raise ValueError("relation endpoints must differ")
        if not 0 <= self.confidence <= 1:
            raise ValueError("relation confidence must be between 0 and 1")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("invalid relation temporal interval")


@dataclass(frozen=True, slots=True)
class Knowledge:
    id: str
    statement: str
    scope: str
    evidence_ids: tuple[str, ...]
    confidence: float
    status: str
    version: int
    created_at: datetime
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    provenance: Provenance = field(default_factory=lambda: Provenance(("unknown",), "unknown"))

    def __post_init__(self) -> None:
        if not self.statement or not self.evidence_ids:
            raise ValueError("knowledge requires statement and evidence")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Behavior:
    id: str
    intent: str
    preconditions: tuple[str, ...]
    context: tuple[str, ...]
    actions: tuple[str, ...]
    expected_outcome: str
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 1.0
    status: str = "active"
    version: int = 1


@dataclass(frozen=True, slots=True)
class RetrievalEvidence:
    object_id: str
    score: float
    lexical_score: float
    semantic_score: float
    temporal_score: float
    relation_score: float
    provenance: Provenance
    lifecycle: MemoryLifecycle
    source_type: str

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 1:
            raise ValueError("score must be between 0 and 1")


def stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"
