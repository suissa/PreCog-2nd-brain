# Checkpoint evidence bundle

Phase 22 provides a reproducible way to retain host-level evidence after the scheduler has been installed and accepted.

Run from the repository root on the target Linux host:

```bash
bash scripts/checkpoint_evidence_bundle.sh
```

To choose the destination explicitly:

```bash
bash scripts/checkpoint_evidence_bundle.sh --output evidence/maintenance-2026-10-21
```

The destination must not already exist. The script refuses to overwrite an existing path (including a symlink), preserving prior evidence. It is read-only with respect to systemd: it does not install, enable, start, stop, restart, or reload units.

The bundle records:
- the user timer listing;
- relevant timer properties;
- relevant oneshot service properties;
- the last 100 journal entries for the checkpoint services;
- capture timestamp, host and user metadata;
- SHA-256 checksums for each evidence file, excluding the checksum manifest itself.

The checksum manifest uses relative filenames. From inside the bundle directory, verify it with:

```bash
sha256sum --check SHA256SUMS
```

The bundle uses `umask 077` so newly created evidence is private to the current user. The capture pipeline redacts common PostgreSQL URL credentials, password/secret/token/private-key assignments, and Authorization bearer/basic values before writing evidence.

This redaction is defense-in-depth, not a proof that arbitrary secrets can never appear in journal text. Review the generated bundle before exporting or attaching it to an external system.

The bundle is operational evidence only. It does not prove audit-history integrity, compromise resistance, or deployment authorization. Audit integrity remains established by the checkpoint verification flow, while deployment authorization remains an independent operational decision.

For an end-to-end host acceptance run, execute the read-only acceptance command first and use `--run-jobs` only when deliberately performing the checkpoint jobs. Preserve the resulting acceptance output and evidence bundle together as the maintenance record.
