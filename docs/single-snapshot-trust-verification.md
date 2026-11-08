# Single-snapshot trust verification

Phase 27 closes a time-of-check/time-of-use gap in authenticated trust-registry verification.

## Verification flow

1. Read the registry and detached signature once.
2. Verify the signature against the independently provisioned Ed25519 root public key.
3. Retain the parsed registry as an in-memory snapshot.
4. Resolve the evidence signer and lifecycle state from that snapshot.
5. Verify the evidence bundle using the selected signer public key.

The CLI never re-opens the registry path between signature validation and signer resolution. The lower-level trust-store API retains its file-loading behavior for callers that intentionally use an unsigned local registry, while the authenticated CLI supplies the verified snapshot explicitly.

## Security boundary

This prevents a registry file replacement between signature verification and trust-policy lookup from changing the policy used by the same verification operation. It does not prevent rollback to an older registry that still has a valid root signature. Rollback resistance still requires an independently retained monotonic sequence/checkpoint or an external trusted policy. Root-key compromise, verifier-host compromise, and replacement of trusted signer public-key files on a compromised host remain outside this phase.

## Regression coverage

The test authenticates a registry, replaces the on-disk path with a different registry, and verifies that signer resolution still uses the authenticated in-memory snapshot.
