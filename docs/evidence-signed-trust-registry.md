# Signed trust registry

Phase 26 authenticates the trust registry itself with a detached Ed25519 signature. The registry signature is verified before any evidence signer key is resolved.

## Trust hierarchy

1. Provision the registry root public key out of band on verifier hosts.
2. Keep the corresponding root private key offline or under a separately controlled administrative signing process.
3. Create a versioned trust registry containing signer public keys and lifecycle states.
4. Sign the exact canonical JSON semantics of that registry. The detached signature is stored as `<registry>.sig`.
5. Verifiers first validate the registry signature, then apply the Phase 25 active/retired/revoked policy and verify the evidence bundle.

## Sign and verify

```bash
python scripts/sign_trust_registry.py /secure/staging/trust-2026-11-08.json \
  --private-key /offline-admin/root-private.pem

python scripts/verify_evidence_trust.py evidence/checkpoint-<timestamp> \
  --trust-store /etc/precog/trust/trust-2026-11-08.json \
  --root-public-key /etc/precog/trust/root-public.pem \
  --key-id ops-2026-a
```

The signing command refuses to overwrite an existing signature. Publish registry updates as new immutable versioned files with matching detached signatures; do not edit a signed registry in place.

## Security boundary and rollback

The root public key must be provisioned independently of the registry and evidence bundle. A valid signature proves that the registry was authorized by the holder of the root private key; it does not protect against compromise of that private key or verifier host. An attacker able to replace a registry with an older, validly signed version may cause rollback. Preventing rollback requires an independently retained monotonic version/checkpoint or trusted external policy; this local file-only phase deliberately does not claim to solve that problem.
