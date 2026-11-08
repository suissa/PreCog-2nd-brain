# Ed25519 attestation for operational evidence

Phase 24 adds a detached signature for evidence bundles created in Phase 22/23. The signature covers canonical JSON containing version, algorithm, key ID, and a sorted mapping of relative file paths to SHA-256 hashes. The attestation itself is excluded from the inventory.

## Key handling

Generate a dedicated Ed25519 keypair outside the evidence directory. Keep the private key offline or in a protected signing environment; distribute the public key through an independently trusted channel. Keep old public keys indexed by key ID for verification after rotation.

Example with OpenSSL:

```bash
openssl genpkey -algorithm ED25519 -out evidence-signing-private.pem
chmod 600 evidence-signing-private.pem
openssl pkey -in evidence-signing-private.pem -pubout -out evidence-signing-public.pem
```

## Sign and verify

Run from the repository root (after installing project dependencies):

```bash
python scripts/attest_evidence_bundle.py sign evidence/checkpoint-<timestamp> \
  --private-key /secure/path/evidence-signing-private.pem --key-id ops-2026-a

python scripts/attest_evidence_bundle.py verify evidence/checkpoint-<timestamp> \
  --public-key /trusted/keys/ops-2026-a.pem --key-id ops-2026-a
```

Signing creates `ATTESTATION.json` with mode 0600 and refuses to overwrite it. Verification fails closed for invalid signatures, mismatched key IDs, missing/extra files, modified content, unsupported format, or symlinked files/directories. Use `--key-id` during verification to bind the signature to the expected trust identity.

## Trust and limits

- The signer must independently trust the public key/key ID; a key shipped beside the bundle is not a trust anchor.
- A valid signature authenticates the inventory and contents against the signer. It does not establish that journal/systemd output is truthful, that the host was uncompromised, or that the evidence author was authorized to deploy.
- Review potentially sensitive evidence before sharing. Phase 22 redaction remains best-effort.
- Rotate keys by assigning a new key ID and retaining old public keys for historical bundles. Do not re-sign historical bundles to erase their original signer identity.
