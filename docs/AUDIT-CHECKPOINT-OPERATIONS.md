# Local audit checkpoint operations

PreCog can create and verify signed promotion-audit checkpoints without cloud services.

## Configure

Set these environment variables for the one-shot command:

- `DATABASE_URL`: PostgreSQL connection string for the promotion audit log.
- `PRECOG_CHECKPOINT_DIR`: directory for immutable signed checkpoint JSON files.
- `PRECOG_PUBLIC_KEY_DIR`: directory containing trusted `<key-id>.pem` public keys.
- `PRECOG_PRIVATE_KEY_FILE`: private Ed25519 PEM file; needed only for creation.
- `PRECOG_PUBLIC_KEY_ID`: key identifier to sign with; needed only for creation.
- `PRECOG_AUDIT_INCIDENT_LOG`: optional local append-only JSONL incident journal.
- `PRECOG_MAX_CHECKPOINT_AGE_SECONDS`: optional maximum checkpoint age enforced by `verify`.

Keep the private signing key outside the repository. The checkpoint directory and incident journal on the same host are not independent evidence against a host/root compromise.

## Run manually

Create or refresh a signed checkpoint, even if the audit head has not changed:

```sh
python scripts/checkpoint_promotion_audit.py create
```

Verify signature, chain reconciliation, and (when configured) freshness:

```sh
PRECOG_MAX_CHECKPOINT_AGE_SECONDS=129600 \
  python scripts/checkpoint_promotion_audit.py verify
```

The example threshold is 36 hours. Choose a threshold that matches the checkpoint creation schedule and expected downtime. Verification exits non-zero and emits an alert for missing, invalid, divergent, future-dated, or stale checkpoints.

## Scheduling

Run `create` on a schedule appropriate to the audit risk (for example, hourly), and run `verify` more frequently (for example, every 15 minutes). Configure the same maximum-age threshold for verification. A scheduler should alert on non-zero exit status; the local incident journal is supplementary and not tamper-proof.

The filesystem store publishes each checkpoint atomically and never overwrites a prior file. Repeated attestations of the same sequence/head use a digest of the signed checkpoint payload in the filename, allowing a newer timestamp to be retained while preserving history.
