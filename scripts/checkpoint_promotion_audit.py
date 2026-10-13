#!/usr/bin/env python3
"""Create or reconcile external promotion-audit checkpoints.

Run this command from cron/systemd. It performs one operation and exits non-zero
on errors. Keep the private key outside the repository and database trust boundary.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("create", "verify"))
    parser.add_argument("--checkpoint-dir", default=os.getenv("PRECOG_CHECKPOINT_DIR"))
    parser.add_argument("--public-key-dir", default=os.getenv("PRECOG_PUBLIC_KEY_DIR"))
    parser.add_argument("--private-key-file", default=os.getenv("PRECOG_PRIVATE_KEY_FILE"))
    parser.add_argument("--public-key-id", default=os.getenv("PRECOG_PUBLIC_KEY_ID"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()

    required = {
        "checkpoint directory": args.checkpoint_dir,
        "public key directory": args.public_key_dir,
        "database URL": args.database_url,
    }
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
        CheckpointJob, FileCheckpointStore, PublicKeyRegistry, StderrAuditAlertSink,
    )
    from precog.postgres_promotion_audit import PostgresPromotionAuditLog

    connection = psycopg.connect(args.database_url)
    try:
        job = CheckpointJob(
            audit_log=PostgresPromotionAuditLog(connection),
            checkpoint_store=FileCheckpointStore(Path(args.checkpoint_dir)),
            public_keys=PublicKeyRegistry(args.public_key_dir),
            alert_sink=StderrAuditAlertSink(),
        )
        if args.operation == "create":
            key_path = Path(args.private_key_file)
            private_key = key_path.read_bytes()
            output = job.create(private_key=private_key, public_key_id=args.public_key_id)
            print(f"Checkpoint written: {output}")
        else:
            result = job.reconcile_latest()
            print(
                f"Checkpoint valid: sequence={result.checkpoint_sequence}, "
                f"current_sequence={result.current_sequence}, "
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
