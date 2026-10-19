# Checkpoint scheduler operational acceptance

The automated suite checks the scheduler's safety contracts, but cannot prove
that a particular Linux host has a working systemd user manager, PostgreSQL
credentials, keys, and writable state directories. Run these checks on the
target host after configuring `~/.config/precog/checkpoint.env`.

Read-only acceptance (does not start jobs or change systemd state):

```bash
bash scripts/checkpoint_systemd_acceptance.sh
```

This requires both `precog-checkpoint-create.timer` and
`precog-checkpoint-verify.timer` to be enabled and active for the current user.
It checks systemd's loaded state as well.

To execute both oneshot services and validate their real end-to-end result:

```bash
bash scripts/checkpoint_systemd_acceptance.sh --run-jobs
```

The second command writes/verifies real checkpoint state and can append an
incident record on failure. Use it only after reviewing the configuration and
choosing an appropriate maintenance window. Inspect logs with:

```bash
journalctl --user -u precog-checkpoint-create.service -u precog-checkpoint-verify.service
```

This acceptance script does not install or enable timers. A passing CI test is
not evidence that the host-level operational run has been performed; retain the
command output and journal excerpt as the deployment evidence.
