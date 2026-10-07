from datetime import datetime, timezone
import json
import pytest
from precog.models import Knowledge, Memory, MemoryLifecycle, MemoryType, Provenance
from precog.projection import MarkdownProjector, ProjectionError

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

def memory() -> Memory:
    return Memory("m1", MemoryType.SEMANTIC, "customer prefers morning", ("e1",), NOW,
        confidence=0.9, salience=0.8, lifecycle=MemoryLifecycle.ACTIVE,
        provenance=Provenance(("e1",), "consolidation"))

def knowledge() -> Knowledge:
    return Knowledge("k1", "Customers prefer morning delivery", "delivery",
        ("m1",), 0.95, "active", 2, NOW,
        provenance=Provenance(("m1",), "consolidation"))

def test_memory_projection_is_deterministic_and_provenance_bearing() -> None:
    projector = MarkdownProjector()
    first = projector.memory(memory())
    second = projector.memory(memory())
    assert first == second
    assert first.path == "memory/m1.md"
    assert '"source_ids":["e1"]' in first.content
    projector.validate(first)

def test_knowledge_projection_is_deterministic() -> None:
    projection = MarkdownProjector().knowledge(knowledge())
    assert projection.path == "knowledge/k1.md"
    assert '"source_ids":["m1"]' in projection.content
    MarkdownProjector().validate(projection)

def test_invalid_frontmatter_is_rejected() -> None:
    projection = MarkdownProjector().memory(memory())
    invalid = projection.__class__(projection.object_type, projection.object_id, projection.path,
        projection.content.replace('"source_ids":["e1"]', '"source_ids":[]'),
        projection.source_ids, projection.version)
    with pytest.raises(ProjectionError):
        MarkdownProjector().validate(invalid)

def test_deleted_projection_can_be_regenerated_from_source() -> None:
    projector = MarkdownProjector()
    original = projector.memory(memory())
    rebuilt = projector.regenerate(memory())
    assert rebuilt == original

def test_frontmatter_is_machine_valid_yaml_json_subset() -> None:
    projection = MarkdownProjector().memory(memory())
    frontmatter = projection.content.split("---\\n", 2)[1].split("\\n---", 1)[0]
    assert json.loads(frontmatter)["object_id"] == "m1"
