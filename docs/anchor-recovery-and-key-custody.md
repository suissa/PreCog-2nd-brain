# Phase 32 — Independent Recovery Checkpoints and Key Custody

## Purpose

A SQLite backup is not a rollback authority. This phase adds a signed recovery checkpoint that must be stored outside the anchor host and signed by a dedicated recovery key. It binds the monotonic registry head and the verified append-only audit-chain head in one snapshot.

## API

`precog.anchor_recovery.create_recovery_checkpoint()` captures, in one SQLite read connection:
- authority identifier and timezone-aware capture timestamp;
- current registry sequence and canonical SHA-256 digest (sequence 0 / null digest before first publication);
- verified audit event count and audit-chain head hash;
- recovery signing key ID and Ed25519 signature over canonical JSON.

`verify_recovery_checkpoint()` verifies the detached signature against an explicitly supplied recovery-key trust map, checks the expected authority identifier, verifies the local audit chain, confirms the local head agrees with the final receipt, and requires exact equality with the independently retained checkpoint. A stale backup, divergent database, unknown key, wrong authority or modified checkpoint fails closed.

Example:

```python
from precog.anchor_recovery import create_recovery_checkpoint, verify_recovery_checkpoint

checkpoint = create_recovery_checkpoint(
    authority, recovery_private_key,
    key_id="anchor-recovery-2026", authority_id="anchor-prod",
)
# Persist checkpoint to a separately administered, append-only destination.
verify_recovery_checkpoint(
    checkpoint, {"anchor-recovery-2026": recovery_public_key}, restored_authority,
    expected_authority_id="anchor-prod",
)
```

The module deliberately does not load private keys from disk, environment variables, a cloud vault or an HSM. Callers must inject the key after retrieving it from an independently controlled custody system. Keep recovery signing keys separate from publisher and online response-signing keys. Retain old public keys to verify historical checkpoints; rotate by provisioning a new key ID and publishing a new checkpoint signed by that key. Revoke a recovery key by removing it from the current trusted-key map for new checkpoint acceptance, while preserving its public key in a separately governed historical verification policy if required.

## Restore procedure (mandatory quarantine)

1. Stop the anchor service and restore the database into a quarantined location.
2. Load the trusted recovery public-key set from independent, read-only custody.
3. Verify the signed recovery checkpoint against the restored database and the expected authority ID.
4. If verification fails or the independent checkpoint cannot be reached, keep the instance offline; do not regenerate a checkpoint from the restored database.
5. After verification, perform a signed-head smoke test, validate ingress/TLS and key permissions, then explicitly authorize service activation.
6. Capture a new recovery checkpoint after the first successful post-restore operation and store it independently.

The checkpoint proves equality to the state captured at its timestamp; it does not prove that the checkpoint store itself is immutable or available. Operational protection requires independent retention (for example, object-lock/WORM storage or a separately administered offline copy), access logging, tested retrieval and separation of duties. A privileged attacker who can replace both the database and the external checkpoint/key trust can still defeat the control.

## Key custody and rotation

- Publisher private keys: held by the publisher's signing workload; authority stores only public keys.
- Online response private key: held by the anchor service runtime or HSM/KMS; verifiers pin the corresponding public key out-of-band. Rotation requires a coordinated verifier trust update and overlap window; this phase does not automate online response-key rotation.
- Recovery private key: dedicated to recovery checkpoint signing, never reused for publisher or response signatures; injected into the API by the custody integration.
- Recovery public keys: versioned by key ID and retained for historical signature verification. A key suspected compromised must be removed from the active acceptance set and a new independently generated key provisioned.
- Never put private key material in the SQLite database, repository, logs, CI variables exposed to build jobs, or recovery checkpoint.

## Operational limits

This is a library-level recovery verification primitive and documented runbook, not an integrated vault, external WORM store, backup scheduler, HSM adapter or deployed recovery drill. The caller must supply an independent checkpoint and trusted public keys. SQLite WAL/FULL and local hash chaining do not by themselves prevent host-level rollback.
