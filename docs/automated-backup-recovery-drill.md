# Automated Backup Verification and Recovery Drill

Phase 33 adds a deterministic, isolated recovery-drill API. It does not schedule backups,
contact an external storage provider, or restore a production service.

## Execution

Call `run_recovery_drill()` with:

- the SQLite anchor database path;
- the independently retained signed checkpoint (never one generated from the backup under test);
- the recovery checkpoint public-key trust map and expected authority ID;
- the publisher public keys and online response signing key needed to open the restored authority;
- a dedicated Ed25519 evidence signing key and evidence key ID.

The drill opens the source database through a read-only SQLite URI and uses
`Connection.backup()` to create a transactionally consistent snapshot. It computes
the backup SHA-256, runs `PRAGMA integrity_check`, copies the snapshot into a fresh
restore target, checks integrity again, initializes an isolated `MonotonicAnchor`,
and verifies the restored state against the external recovery checkpoint.

The source database is never used as the verification target. Temporary backup and
restore files are removed when the drill completes. A failed checkpoint verification
does not create or refresh a recovery checkpoint.

## Signed evidence

The returned envelope contains `key_id`, a canonical JSON `payload`, and a detached
Ed25519 signature. The payload records only the run ID, authority ID, pass/fail status,
a bounded reason code, checkpoint and backup SHA-256 digests, the verified restored
state (only on success), and UTC start/completion timestamps. It does not include
registry contents, database paths, SQL errors, or key material.

Use `verify_recovery_drill_evidence()` with a separately provisioned evidence-key
trust map. A valid evidence signature authenticates the report; consumers must still
require `status == "passed"`. The evidence signer should be distinct from publisher,
online response, and recovery checkpoint signers. The API cannot prove key separation
when callers load the same underlying private key into different objects; provisioning
and custody policy must enforce it.

## Failure behavior

The drill fails closed for a missing checkpoint, unavailable source database,
corrupt SQLite backup, stale/divergent restored state, unknown recovery signer,
invalid checkpoint signature, or authority mismatch. Failure reports are signed too,
so operators can retain evidence of unsuccessful drills without exposing operational
details. An unavailable or malformed checkpoint must never be replaced with a newly
generated checkpoint during the same drill.

## Operational boundary

CI exercises temporary local SQLite databases only. It does not prove that an
independent backup provider, WORM retention, vault/HSM, scheduler, production host,
network partition, or disaster-recovery site is correctly configured. Store the
checkpoint and signed drill evidence outside the authority host and periodically
perform a separately authorized restore exercise in the target recovery environment.
