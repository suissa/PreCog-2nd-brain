# Local audit checkpoint operations

PreCog can create and verify signed promotion-audit checkpoints without cloud services.

## Install safely

From the repository root:

```sh
bash scripts/install_checkpoint_systemd.sh "$PWD"
```

The installer writes user-level units under `~/.config/systemd/user` and creates `~/.config/precog/checkpoint.env` with mode `0600`. If it creates a new template, it installs the units but deliberately does not enable timers. Fill in the configuration and run the installer again; it runs preflight validation and enables timers only if every check passes.

Required settings include `DATABASE_URL`, checkpoint and trusted public-key directories, the private signing key path, `PRECOG_PUBLIC_KEY_ID`, and `PRECOG_PYTHON`. The configured interpreter must be the absolute path to the project's Python environment with the PostgreSQL extra installed. The template's `/usr/bin/python3` is only a default, not a guarantee that dependencies are available.

## Preflight checks

`scripts/checkpoint_preflight.py` checks that the repository and interpreter exist, configuration values are present, the freshness threshold is positive, checkpoint and incident-log paths are writable, the configured Ed25519 private/public keys are readable and match, the private key is not group/world accessible on POSIX, and PostgreSQL accepts a short `SELECT 1` connection probe. Connection exceptions are deliberately summarized by type so credentials in a database URL are not printed.

Run the same check manually after changing configuration:

```sh
set -a
source "$HOME/.config/precog/checkpoint.env"
set +a
"$PRECOG_PYTHON" "$PRECOG_REPO_DIR/scripts/checkpoint_preflight.py"
```

Preflight validates readiness but does not create a checkpoint or prove that audit history is consistent; the scheduled `create` and `verify` operations remain responsible for those checks.

## Schedule and inspect

After preflight succeeds, the installer enables two timers:

- `precog-checkpoint-create.timer`: creates a signed checkpoint hourly.
- `precog-checkpoint-verify.timer`: verifies integrity and freshness every 15 minutes.

```sh
systemctl --user list-timers 'precog-checkpoint-*'
systemctl --user start precog-checkpoint-create.service
systemctl --user start precog-checkpoint-verify.service
journalctl --user -u precog-checkpoint-create.service -u precog-checkpoint-verify.service
```

The default `PRECOG_MAX_CHECKPOINT_AGE_SECONDS=129600` is a 36-hour example threshold. Choose a value appropriate to the schedule and downtime tolerance. The optional `PRECOG_AUDIT_INCIDENT_LOG` records local JSONL incidents; non-zero service results remain visible in the systemd journal.

The installer does not enable user lingering or modify host-wide policy. On a machine where the user is not continuously logged in, decide explicitly whether lingering is permitted. User-level units are not an independent security boundary against compromise of the account or host.

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

Verification exits non-zero and emits an alert for missing, invalid, divergent, future-dated, or stale checkpoints. The filesystem store publishes each checkpoint atomically and never overwrites a prior file.
