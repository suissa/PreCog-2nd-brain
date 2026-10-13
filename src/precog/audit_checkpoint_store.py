from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .audit_checkpoint import PromotionAuditCheckpoint


class CheckpointPublisher(Protocol):
    """Durable external destination for signed audit checkpoint manifests."""

    def publish(self, checkpoint: PromotionAuditCheckpoint) -> str:
        """Publish without replacing an existing checkpoint; return its locator."""


@dataclass(frozen=True, slots=True)
class S3CheckpointPublisher:
    """Publish checkpoints to S3 using create-only writes and an injected client."""

    client: Any
    bucket: str
    prefix: str = "precog/promotion-audit/checkpoints"

    def __post_init__(self) -> None:
        if not self.bucket.strip():
            raise ValueError("S3 bucket must be non-empty")
        normalized = self.prefix.strip("/")
        if not normalized.strip():
            raise ValueError("S3 prefix must be non-empty")
        object.__setattr__(self, "prefix", normalized)

    def publish(self, checkpoint: PromotionAuditCheckpoint) -> str:
        timestamp = checkpoint.created_at.replace(":", "-")
        key = (
            f"{self.prefix}/"
            f"{checkpoint.sequence:020d}-{checkpoint.head_hash}-{timestamp}.json"
        )
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=checkpoint.to_json().encode("utf-8"),
            ContentType="application/json",
            Metadata={
                "checkpoint-sequence": str(checkpoint.sequence),
                "checkpoint-head-hash": checkpoint.head_hash,
                "checkpoint-key-id": checkpoint.public_key_id,
            },
            IfNoneMatch="*",
        )
        return f"s3://{self.bucket}/{key}"
