from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, Sequence

from .models import Memory


class EmbeddingProvider(Protocol):
    """Provider-neutral boundary for generating embeddings."""

    @property
    def model(self) -> str:
        ...

    @property
    def version(self) -> str:
        ...

    @property
    def dimensions(self) -> int:
        ...

    def embed(self, text: str) -> Sequence[float]:
        ...


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    """Rebuildable vector projection of a canonical Memory."""

    memory_id: str
    vector: tuple[float, ...]
    model: str
    provider_version: str
    dimensions: int
    source_version: int
    source_hash: str

    def __post_init__(self) -> None:
        if not self.memory_id:
            raise ValueError("memory_id must be non-empty")
        if not self.model or not self.provider_version:
            raise ValueError("embedding model and provider_version are required")
        if self.dimensions < 1:
            raise ValueError("embedding dimensions must be >= 1")
        if len(self.vector) != self.dimensions:
            raise ValueError("embedding vector dimension mismatch")
        if self.source_version < 1:
            raise ValueError("source_version must be >= 1")
        if len(self.source_hash) != 64:
            raise ValueError("source_hash must be a SHA-256 digest")


def memory_source_hash(memory: Memory) -> str:
    """Stable source fingerprint; derived vectors can always be rebuilt from Memory."""
    canonical = "\x1f".join((
        memory.id,
        memory.content,
        str(memory.version),
        memory.schema_version.__str__(),
    ))
    return sha256(canonical.encode("utf-8")).hexdigest()


def build_embedding(memory: Memory, provider: EmbeddingProvider) -> EmbeddingRecord:
    vector = tuple(float(value) for value in provider.embed(memory.content))
    if len(vector) != provider.dimensions:
        raise ValueError(
            f"embedding provider returned {len(vector)} dimensions; "
            f"expected {provider.dimensions}"
        )
    return EmbeddingRecord(
        memory_id=memory.id,
        vector=vector,
        model=provider.model,
        provider_version=provider.version,
        dimensions=provider.dimensions,
        source_version=memory.version,
        source_hash=memory_source_hash(memory),
    )


def is_embedding_current(memory: Memory, embedding: EmbeddingRecord) -> bool:
    return (
        embedding.memory_id == memory.id
        and embedding.source_version == memory.version
        and embedding.source_hash == memory_source_hash(memory)
    )


class DeterministicEmbeddingProvider:
    """Small reference provider for tests and local deterministic rebuilds."""

    def __init__(self, dimensions: int = 8, model: str = "deterministic") -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be >= 1")
        self._dimensions = dimensions
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    @property
    def version(self) -> str:
        return "1"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> Sequence[float]:
        digest = sha256((self._model + "\x1f" + text).encode("utf-8")).digest()
        values = []
        for index in range(self._dimensions):
            values.append((digest[index % len(digest)] / 255.0) * 2.0 - 1.0)
        return values
