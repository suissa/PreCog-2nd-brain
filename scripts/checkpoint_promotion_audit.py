#!/usr/bin/env python3
"""Create or reconcile external promotion-audit checkpoints.

Run this command from cron/systemd or a scheduler. It performs one operation and
exits non-zero on errors. Keep the private key outside the repository and database
trust boundary. Verification also enforces configurable freshness/lag thresholds.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from precog.audit_checkpoint_monitoring import validate_checkpoint_freshness


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("create", "verify"))
    parser.add_argument("--checkpoint-backend", choices=("file", "s3"), default=os.getenv("PRECOG_CHECKPOINT_BACKEND", "file"))
    parser.add_argument("--checkpoint-dir", default=os.getenv("PRECOG_CHECKPOINT_DIR"))
    parser.add_argument("--s3-bucket", default=os.getenv("PRECOG_AUDIT_S3_BUCKET"))
    parser.add_argument("--s3-prefix", default=os.getenv("PRECOG_AUDIT_S3_PREFIX", "precog/promotion-audit/checkpoints"))
    parser.add_argument("--aws-region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--public-key-dir", default=os.getenv("PRECOG_PUBLIC_KEY_DIR"))
    parser.add_argument("--private-key-file", default=os.getenv("PRECOG_PRIVATE_KEY_FILE"))
    parser.add_argument("--public-key-id", default=os.getenv("PRECOG_PUBLIC_KEY_ID"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--max-checkpoint-age-hours", type=float, default=float(os.getenv("PRECOG_MAX_CHECKPOINT_AGE_HOURS", "36")))
    parser.add_argument("--max-checkpoint-lag-events", type=int, default=int(os.getenv("PRECOG_MAX_CHECKPOINT_LAG_EVENTS", "1000")))
    args = parser.parse_args()

    if args.max_checkpoint_age_hours <= 0:
        parser.error("--max-checkpoint-age-hours must be greater than zero")
    if args.max_checkpoint_lag_events < 0:
        parser.error("--max-checkpoint-lag-events must be non-negative")

    required = {"public key directory": args.public_key_dir, "database URL": args.database_url}
    if args.checkpoint_backend == "file":
        required["checkpoint directory"] = args.checkpoint_dir
    else:
        required["S3 bucket"] = args.s3_bucket
    if args.operation == "create":
        required["private key file"] = args.private_key_file
        required["public key ID"] = args.public_key_id
    missing = [name for name, value in required.items() if not value]
    if missing:
        parser.error("missing configuration: " + ", ".join(missing))

    try:
        import psycopg
    except ImportError:
        print("Install the PostgreSQL adapter with: pip install 'psycopg[binary]>=3.2'", file=sys.stderr)
        return 2

    from precog.audit_checkpoint_ops import (
        CheckpointJob, FileCheckpointStore, PublicKeyRegistry, S3CheckpointStore, StderrAuditAlertSink,
    )
    from precog.postgres_promotion_audit import PostgresPromotionAuditLog

    if args.checkpoint_backend == "s3":
        try:
            import boto3
        except ImportError:
            print("Install the S3 adapter with: pip install 'boto3>=1.35'", file=sys.stderr)
            return 2
        store = S3CheckpointStore(
            boto3.client("s3", region_name=args.aws_region),
            bucket=args.s3_bucket,
            prefix=args.s3_prefix,
        )
    else:
        store = FileCheckpointStore(Path(args.checkpoint_dir))

    connection = psycopg.connect(args.database_url)
    try:
        job = CheckpointJob(
            audit_log=PostgresPromotionAuditLog(connection),
            checkpoint_store=store,
            public_keys=PublicKeyRegistry(args.public_key_dir),
            alert_sink=StderrAuditAlertSink(),
        )
        if args.operation == "create":
            private_key = Path(args.private_key_file).read_bytes()
            output = job.create(private_key=private_key, public_key_id=args.public_key_id)
            print(f"Checkpoint written: {output}")
        else:
            result = job.reconcile_latest()
            checkpoint = store.latest()
            if checkpoint is None:
                raise RuntimeError("no external audit checkpoint is available")
            validate_checkpoint_freshness(
                checkpoint,
                current_sequence=result.current_sequence,
                max_age_hours=args.max_checkpoint_age_hours,
                max_lag_events=args.max_checkpoint_lag_events,
            )
            lag = result.current_sequence - result.checkpoint_sequence
            print(
                f"Checkpoint valid and fresh: sequence={result.checkpoint_sequence}, "
                f"current_sequence={result.current_sequence}, lag_events={lag}, "
                f"head={result.current_head_hash}"
            )
        return 0
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
