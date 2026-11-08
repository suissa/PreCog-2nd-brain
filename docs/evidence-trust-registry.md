# Trusted key registry and revocation

Phase 25 adds a local trust registry for operational evidence signers. Unlike the direct verifier, this path resolves the attestation's `key_id` only through an independently provisioned registry and applies an explicit key lifecycle policy.

## Registry format

Store `trust.json` and its public-key files in a directory controlled by the verifier:

```json
{
  "version": 1,
  "keys": {
    "ops-2026-a": {
      "public_key": "keys/ops-2026-a.pem",
      "status": "active"
    },
    "ops-2025-retired": {
      "public_key": "keys/ops-2025-retired.pem",
      "status": "retired"
    },
    "ops-compromised": {
      "public_key": "keys/ops-compromised.pem",
      "status": "revoked"
    }
  }
}
```

Statuses have intentionally strict meanings:
- `active`: may verify newly produced and historical bundles.
- `retired`: cannot be used for new signing, but remains accepted for historical verification.
- `revoked`: all bundles signed by this key fail trust verification, including historical bundles. If incident response requires a more nuanced cutoff, use a separately reviewed policy extension rather than silently accepting revoked signatures.

Unknown keys, unknown statuses, malformed registries, path traversal, symlinked key files, and mismatched expected key IDs fail closed.

## Verify

```bash
python scripts/verify_evidence_trust.py evidence/checkpoint-<timestamp> \
  --trust-store /etc/precog/trust/trust.json \
  --key-id ops-2026-a
```

The trust directory and registry must be provisioned through an independently trusted administrative process. Do not take a registry or public key from the evidence bundle itself. Restrict write access to the trust directory; back it up and review every lifecycle change. This implementation validates local file structure and policy, but does not cryptographically sign the registry, provide remote revocation distribution, or protect against an attacker who controls the verifier host or its trust directory.

## Rotation and incident response

1. Add a new key ID and public key with status `active`.
2. Change the old key to `retired` after signing has moved to the new key.
3. Keep retired public keys available for historical verification.
4. Set a compromised key to `revoked` and investigate all artifacts attributed to it.
5. Preserve registry change history in the organization's independently controlled audit system.
