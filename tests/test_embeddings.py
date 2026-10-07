from datetime import datetime, timezone

import pytest

from precog.embeddings import (
    DeterministicEmbeddingProvider,
    build_embedding,
    is_embedding_current,
)
from precog.models import Memory, MemoryType, Provenance

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def make_memory(version=1, content="payment failed"):
    return Memory(
        "m1", MemoryType.SEMANTIC, content, ("e1",), NOW,
        provenance=Provenance(("e1",), "test"), version=version,
    )


def test_insert_and_searchable_embedding_metadata():
    provider = DeterministicEmbeddingProvider(4)
    record = build_embedding(make_memory(), provider)
    assert len(record.vector) == 4
    assert record.model == "deterministic"
    assert record.provider_version == "1"
    assert record.dimensions == 4
    assert record.source_version == 1
    assert len(record.source_hash) == 64


def test_provider_failure_does_not_mutate_memory():
    class FailingProvider(DeterministicEmbeddingProvider):
        def embed(self, text):
            raise RuntimeError("provider unavailable")

    memory = make_memory()
    with pytest.raises(RuntimeError, match="provider unavailable"):
        build_embedding(memory, FailingProvider(4))
    assert memory.version == 1
    assert memory.content == "payment failed"


def test_dimension_mismatch_is_rejected():
    class WrongSizeProvider(DeterministicEmbeddingProvider):
        def embed(self, text):
            return (1.0, 2.0)

    with pytest.raises(ValueError, match="dimension"):
        build_embedding(make_memory(), WrongSizeProvider(4))


def test_source_version_change_marks_vector_stale_and_rebuilds():
    provider = DeterministicEmbeddingProvider(4)
    original = make_memory()
    record = build_embedding(original, provider)
    changed = make_memory(version=2, content="payment recovered")
    assert not is_embedding_current(changed, record)
    rebuilt = build_embedding(changed, provider)
    assert rebuilt.source_version == 2
    assert rebuilt.source_hash != record.source_hash
    assert is_embedding_current(changed, rebuilt)


def test_provider_can_be_replaced():
    first = build_embedding(make_memory(), DeterministicEmbeddingProvider(4, "model-a"))
    second = build_embedding(make_memory(), DeterministicEmbeddingProvider(4, "model-b"))
    assert first.model != second.model
    assert first.vector != second.vector
