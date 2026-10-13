from datetime import datetime, timezone

import pytest

from precog.audit_checkpoint import PromotionAuditCheckpoint
from precog.audit_checkpoint_store import S3CheckpointPublisher


class FakeS3:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def put_object(self, **kwargs: object) -> dict[str, str]:
        self.calls.append(kwargs)
        return {"ETag": '"test"'}


def checkpoint() -> PromotionAuditCheckpoint:
    return PromotionAuditCheckpoint(
        version=1,
        sequence=23,
        head_hash="a" * 64,
        checked_events=23,
        legacy_unhashed_events=0,
        created_at=datetime(2026, 10, 13, tzinfo=timezone.utc).isoformat(),
        public_key_id="audit-key-2026-02",
        signature="signed-manifest",
    )


def test_s3_publisher_writes_immutable_object_with_audit_metadata() -> None:
    client = FakeS3()
    publisher = S3CheckpointPublisher(client, "audit-evidence", "/external/checkpoints/")
    locator = publisher.publish(checkpoint())

    assert locator.startswith("s3://audit-evidence/external/checkpoints/")
    request = client.calls[0]
    assert request["IfNoneMatch"] == "*"
    assert request["ContentType"] == "application/json"
    assert request["Metadata"] == {
        "checkpoint-sequence": "23",
        "checkpoint-head-hash": "a" * 64,
        "checkpoint-key-id": "audit-key-2026-02",
    }
    assert b'"signature": "signed-manifest"' in request["Body"]  # type: ignore[operator]


def test_s3_publisher_rejects_empty_bucket_or_prefix() -> None:
    client = FakeS3()
    with pytest.raises(ValueError, match="bucket"):
        S3CheckpointPublisher(client, " ")
    with pytest.raises(ValueError, match="prefix"):
        S3CheckpointPublisher(client, "audit-evidence", "/ /")


def test_s3_publisher_lets_conditional_write_conflicts_fail_closed() -> None:
    class ConflictS3:
        def put_object(self, **kwargs: object) -> None:
            assert kwargs["IfNoneMatch"] == "*"
            raise RuntimeError("precondition failed")

    publisher = S3CheckpointPublisher(ConflictS3(), "audit-evidence")
    with pytest.raises(RuntimeError, match="precondition failed"):
        publisher.publish(checkpoint())
