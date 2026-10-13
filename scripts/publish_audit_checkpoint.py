from __future__ import annotations

import os
from pathlib import Path

import boto3
import psycopg

from precog.audit_checkpoint_store import S3CheckpointPublisher
from precog.postgres_promotion_audit import PostgresPromotionAuditLog


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"required environment variable is missing: {name}")
    return value


def main() -> int:
    database_url = required("PRECOG_DATABASE_URL")
    private_key_path = Path(required("PRECOG_AUDIT_PRIVATE_KEY_PATH"))
    key_id = required("PRECOG_AUDIT_KEY_ID")
    bucket = required("PRECOG_AUDIT_S3_BUCKET")
    region = os.environ.get("AWS_REGION", "us-east-1").strip() or "us-east-1"
    prefix = os.environ.get(
        "PRECOG_AUDIT_S3_PREFIX", "precog/promotion-audit/checkpoints"
    )

    private_key = private_key_path.read_bytes()
    s3 = boto3.client("s3", region_name=region)
    publisher = S3CheckpointPublisher(client=s3, bucket=bucket, prefix=prefix)

    with psycopg.connect(database_url) as connection:
        audit_log = PostgresPromotionAuditLog(connection)
        checkpoint = audit_log.export_checkpoint(
            private_key=private_key,
            public_key_id=key_id,
        )
        locator = publisher.publish(checkpoint)

    print(
        "Published signed audit checkpoint: "
        f"sequence={checkpoint.sequence} "
        f"head_hash={checkpoint.head_hash} "
        f"key_id={checkpoint.public_key_id} "
        f"locator={locator}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
