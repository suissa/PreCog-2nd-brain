# External Backup Storage and Retention

Phase 34 introduces a provider-neutral `ObjectStore` contract and signed archive
manifests. It archives the SQLite backup, its independently signed recovery
checkpoint, and a signed manifest as three immutable, content-addressed objects.

## Archive flow

`archive_recovery_backup()` captures a consistent SQLite snapshot through the
online backup API. It verifies SQLite integrity and validates the supplied
Phase-32 checkpoint against that exact snapshot before uploading anything. The
backup and checkpoint are SHA-256 addressed; the signed manifest binds both keys
and hashes, byte size, authority ID, monotonic sequence, creation time and
retention deadline.

Objects are uploaded conditionally (create-if-absent), with the manifest written
last. A partial upload can leave unreferenced content-addressed objects, but
cannot publish a manifest that points to missing objects. Repeating the same
archive is idempotent when the adapter honors conditional-create semantics.

## Restore and history

`restore_archived_backup()` verifies the manifest signature and authority,
checks stored object retention metadata, verifies both content hashes and backup
size, then restores to a new temporary file. It runs SQLite integrity validation
and verifies the archived checkpoint against the restored authority before
atomically moving the verified database to the requested target. Existing targets
are never overwritten.

`list_archived_manifests()` returns verified historical manifests newest-first.
It fails closed if an indexed manifest has an invalid digest, malformed payload,
unknown signer or invalid signature. `prune_expired_objects()` requests deletion
only after each object's retention deadline. The backend must independently
enforce retention and reject early deletion.

## Adapter and key requirements

The `ObjectStore` protocol requires `put_if_absent`, `get`, `list` and
retention-aware `delete`. A production adapter must map these operations to a
separate storage account/domain, use conditional object creation, return the
provider's effective retention deadline, enforce object lock/WORM server-side,
and protect credentials with least privilege. The included
`InMemoryObjectStore` exists only for tests; it is neither durable nor an
independent failure domain.

Manifest signing keys must be distinct from publisher, online response and
recovery checkpoint keys. Key provisioning and separation remain deployment
responsibilities. Never store private signing keys beside the backup objects.

## Operational boundary

CI validates the protocol contract, signed manifests, immutable content addressing,
tamper detection, historical listing, restore verification, and retention behavior
using an in-memory test adapter. It does not configure or prove a cloud bucket,
WORM/object-lock policy, cross-region replication, IAM, encryption-at-rest,
provider credentials, lifecycle scheduler or external disaster-recovery site.
Production adapters must pass the same contract tests against their provider.
