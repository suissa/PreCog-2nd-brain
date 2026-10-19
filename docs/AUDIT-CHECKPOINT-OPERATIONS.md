# Local audit checkpoint operations

PreCog can create and verify signed promotion-audit checkpoints without cloud services.

## Configure and install the local scheduler

From the repository root, install the user-level `systemd` timers:

```sh
bash scripts/install_checkpoint_systemd.sh "$PWD"
```

The installer writes units under `~/.config/systemd/user`, creates a private configuration template at `~/.config/precog/checkpoint.env` (mode `0600`), and enables two timers:

- `precog-checkpoint-create.timer`: creates a signed checkpoint hourly.
- `precog-checkpoint-verify.timer`: verifies integrity and freshness every 15 minutes.

Edit the environment file before the first run. Set `DATABASE_URL`, the checkpoint and trusted public-key directories, the private signing key path, and `PRECOG_PUBLIC_KEY_ID`. The generated defaults are examples, not working credentials or provisioned keys. Install the project and its PostgreSQL extra in the Python environment used by the service. `PRECOG_PYTHON` selects the interpreter (default template: `/usr/bin/python3`); set it to the absolute path of the project's virtual-environment interpreter if dependencies are installed there.

The configured `PRECOG_MAX_CHECKPOINT_AGE_SECONDS=129600` is a 36-hour example threshold. Choose a value that matches your schedule and downtime tolerance. The verification timer's failures are visible in the systemd journal; when configured, the application also appends incidents to `PRECOG_AUDIT_INCIDENT_LOG`. A non-zero service result should be connected to an alerting mechanism appropriate to the host.

Check the timers and logs:

```sh
systemctl --user list-timers 'precog-checkpoint-*'
systemctl --user start precog-checkpoint-create.service
systemctl --user start precog-checkpoint-verify.service
journalctl --user -u precog-checkpoint-create.service -u precog-checkpoint-verify.service
```

The installer does not enable user lingering. On a machine where the user is not continuously logged in, decide explicitly whether to enable it with the administrator's policy. User-level units are not an independent security boundary against compromise of that user's account or host.

## Configure manually

Set these environment variables for the one-shot command:

- `DATABASE_URL`: PostgreSQL connection string for the promotion audit log.
- `PRECOG_CHECKPOINT_DIR`: directory for immutable signed checkpoint JSON files.
- `PRECOG_PUBLIC_KEY_DIR`: directory containing trusted `<key-id>.pem` public keys.
- `PRECOG_PRIVATE_KEY_FILE`: private Ed25519 PEM file; needed only for creation.
- `PRECOG_PUBLIC_KEY_ID`: key identifier to sign with; needed only for creation.
- `PRECOG_AUDIT_INCIDENT_LOG`: optional local append-only JSONL incident journal.
- `PRECOG_MAX_CHECKPOINT_AGE_SECONDS`: optional maximum checkpoint age enforced by `verify`.

Keep the private signing key outside the repository. The checkpoint directory and incident journal on the same host are not independent evidence against a host/root compromise.

Create or refresh a signed checkpoint:

```sh
python scripts/checkpoint_promotion_audit.py create
```

Verify signature, chain reconciliation, and configured freshness:

```sh
PRECOG_MAX_CHECKPOINT_AGE_SECONDS=129600 \
  python scripts/checkpoint_promotion_audit.py verify
```

Verification exits non-zero and emits an alert for missing, invalid, divergent, future-dated, or stale checkpoints. The filesystem store publishes each checkpoint atomically and never overwrites a prior file. Repeated attestations of the same sequence/head use a digest of the signed payload in the filename, preserving history.
