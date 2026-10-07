from __future__ import annotations
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from .models import Knowledge, Memory

class ProjectionError(ValueError):
    pass

@dataclass(frozen=True, slots=True)
class MarkdownProjection:
    object_type: str
    object_id: str
    path: str
    content: str
    source_ids: tuple[str, ...]
    version: int

def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None

def _safe_segment(value: str) -> str:
    if not value or value in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ProjectionError("object id is not a safe deterministic path segment")
    return value

def _frontmatter(projection: MarkdownProjection) -> str:
    data = {
        "object_id": projection.object_id,
        "object_type": projection.object_type,
        "projection_version": 1,
        "source_ids": list(projection.source_ids),
        "source_version": projection.version,
    }
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _memory_body(memory: Memory) -> str:
    metadata = json.dumps(memory.metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "\n".join([
        "# Memory " + memory.id, "",
        "**Type:** " + memory.memory_type.value, "**Lifecycle:** " + memory.lifecycle.value,
        "**Confidence:** {:.6f}".format(memory.confidence),
        "**Salience:** {:.6f}".format(memory.salience),
        "**Created:** " + str(_timestamp(memory.created_at)),
        "**Valid from:** " + str(_timestamp(memory.valid_from)),
        "**Valid to:** " + str(_timestamp(memory.valid_to)), "",
        "## Content", "", memory.content, "",
        "## Provenance", "",
        "Derivation: " + memory.provenance.derivation,
        "Sources: " + ", ".join(memory.source_ids), "",
        "## Metadata", "", metadata, ""
    ])

def _knowledge_body(knowledge: Knowledge) -> str:
    return "\n".join([
        "# Knowledge " + knowledge.id, "",
        "**Scope:** " + knowledge.scope, "**Status:** " + knowledge.status,
        "**Confidence:** {:.6f}".format(knowledge.confidence),
        "**Version:** " + str(knowledge.version),
        "**Created:** " + str(_timestamp(knowledge.created_at)),
        "**Valid from:** " + str(_timestamp(knowledge.valid_from)),
        "**Valid to:** " + str(_timestamp(knowledge.valid_to)), "",
        "## Statement", "", knowledge.statement, "",
        "## Evidence", "", *["- " + item for item in knowledge.evidence_ids], "",
        "## Provenance", "",
        "Derivation: " + knowledge.provenance.derivation,
        "Sources: " + ", ".join(knowledge.provenance.source_ids), ""
    ])

class MarkdownProjector:
    """Deterministic, read-only projection of derived objects."""

    def memory(self, memory: Memory) -> MarkdownProjection:
        projection = MarkdownProjection("memory", memory.id, "memory/" + _safe_segment(memory.id) + ".md",
            "", tuple(memory.source_ids), memory.version)
        return MarkdownProjection(projection.object_type, projection.object_id, projection.path,
            "---\n" + _frontmatter(projection) + "\n---\n\n" + _memory_body(memory),
            projection.source_ids, projection.version)

    def knowledge(self, knowledge: Knowledge) -> MarkdownProjection:
        projection = MarkdownProjection("knowledge", knowledge.id, "knowledge/" + _safe_segment(knowledge.id) + ".md",
            "", tuple(knowledge.evidence_ids), knowledge.version)
        return MarkdownProjection(projection.object_type, projection.object_id, projection.path,
            "---\n" + _frontmatter(projection) + "\n---\n\n" + _knowledge_body(knowledge),
            projection.source_ids, projection.version)

    def validate(self, projection: MarkdownProjection) -> None:
        parts = projection.content.split("\n")
        if len(parts) < 4 or parts[0] != "---":
            raise ProjectionError("missing YAML frontmatter")
        try:
            end = parts.index("---", 1)
            data: Any = json.loads("\n".join(parts[1:end]))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ProjectionError("invalid YAML frontmatter") from exc
        required = {"object_id", "object_type", "projection_version", "source_ids", "source_version"}
        if not isinstance(data, dict) or set(data) != required:
            raise ProjectionError("frontmatter schema mismatch")
        if data["object_id"] != projection.object_id or data["object_type"] != projection.object_type:
            raise ProjectionError("frontmatter identity mismatch")
        if not isinstance(data["source_ids"], list) or not data["source_ids"]:
            raise ProjectionError("frontmatter provenance is required")
        if data["source_version"] != projection.version:
            raise ProjectionError("frontmatter version mismatch")
        expected = projection.object_type + "/" + _safe_segment(projection.object_id) + ".md"
        if projection.path != expected:
            raise ProjectionError("non-deterministic projection path")

    def regenerate(self, source: Memory | Knowledge) -> MarkdownProjection:
        rebuilt = self.memory(source) if isinstance(source, Memory) else self.knowledge(source)
        self.validate(rebuilt)
        return rebuilt

def project_memory(memory: Memory) -> MarkdownProjection:
    return MarkdownProjector().memory(memory)

def project_knowledge(knowledge: Knowledge) -> MarkdownProjection:
    return MarkdownProjector().knowledge(knowledge)
