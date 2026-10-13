from datetime import datetime, timezone
from io import BytesIO

import pytest

from precog.audit_checkpoint import PromotionAuditCheckpoint
from precog.audit_checkpoint_ops import S3CheckpointStore


def make_checkpoint(sequence: int, head: str) -> PromotionAuditCheckpoint:
    return PromotionAuditCheckpoint(
        version=1,
        sequence=sequence,
        head_hash=head * 64,
        checked_events=sequence,
        legacy_unhashed_events=0,
        created_at=datetime(2026, 10, 13, sequence % 24, tzinfo=timezone.utc).isoformat(),
        public_key_id="audit-key",
        signature=f"signature-{sequence}",
    )


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_requests: list[dict[str, object]] = []

    def put_object(self, **kwargs: object) -> dict[str, str]:
        key = str(kwargs["Key"])
        if key in self.objects:
            raise RuntimeError("precondition failed")
        self.objects[key] = kwargs["Body"]  # type: ignore[assignment]
        self.put_requests.append(kwargs)
        return {"ETag": '"test"'}

    def list_objects_v2(self, **kwargs: object) -> dict[str, object]:
        prefix = str(kwargs["Prefix"])
        keys = sorted(key for key in self.objects if key.startswith(prefix))
        return {"Contents": [{"Key": key} for key in keys], "IsTruncated": False}

    def get_object(self, **kwargs: object) -> dict[str, BytesIO]:
        return {"Body": BytesIO(self.objects[str(kwargs["Key"])])}


def test_s3_store_publishes_create_only_and_loads_latest_checkpoint() -> None:
    client = FakeS3()
    store = S3CheckpointStore(client, "precog-audit", "/checkpoints/")
    first = make_checkpoint(1, "a")
    latest = make_checkpoint(2, "b")

    locator = store.write(first)
    store.write(latest)

    assert locator.startswith("s3://precog-audit/checkpoints/")
    assert client.put_requests[0]["IfNoneMatch"] == "*"
    assert client.put_requests[0]["ContentType"] == "application/json"
    assert store.latest() == latest


def test_s3_store_fails_closed_on_object_collision() -> None:
    client = FakeS3()
    store = S3CheckpointStore(client, "precog-audit")
    checkpoint = make_checkpoint(1, "a")
    store.write(checkpoint)
    with pytest.raises(RuntimeError, match="precondition failed"):
        store.write(checkpoint)


def test_s3_store_requires_bucket_and_prefix() -> None:
    client = FakeS3()
    with pytest.raises(ValueError, match="bucket"):
        S3CheckpointStore(client, " ")
    with pytest.raises(ValueError, match="prefix"):
        S3CheckpointStore(client, "precog-audit", " / ")
