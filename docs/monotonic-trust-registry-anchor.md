# Monotonic trust-registry anchor

Phase 28 adds client-side enforcement of an independently operated monotonic trust-registry head. The local registry remains Ed25519-signed by its registry root. The anchor uses a separate Ed25519 public key provisioned out-of-band.

## Registry format

Anchored registries must include a positive integer `sequence` in the root JSON object. The sequence is covered by the registry-root signature. Each published version is immutable.

## Read protocol

The verifier performs an HTTPS GET to:

```
GET {anchor-url}/v1/trust-registry/head?nonce={fresh-random-nonce}
Accept: application/json
Cache-Control: no-store
```

The service returns:

```json
{
  "payload": {
    "version": 1,
    "sequence": 28,
    "registry_sha256": "<sha256-of-canonical-registry-json>",
    "nonce": "<same-request-nonce>"
  },
  "signature": "<base64-ed25519-signature-of-canonical-payload>"
}
```

Canonical JSON uses sorted keys, compact separators, UTF-8 and no ASCII escaping. The verifier validates HTTPS, the nonce, the anchor signature, sequence and exact registry digest. A lower sequence, higher sequence, or same-sequence content mismatch fails closed. The nonce prevents a cached or replayed signed head response from satisfying a new verification request.

## Anchor service requirements

The service is an independent trust boundary and must:
- authenticate and authorize registry publishers separately from read-only verifiers;
- atomically advance the head only when the new sequence is greater than the stored sequence;
- reject same-sequence/different-digest writes and all lower-sequence writes;
- retain its state outside the verifier host and outside the registry publisher's write control;
- sign responses with a dedicated Ed25519 key whose public key is provisioned independently;
- provide durable backups and auditable operator-controlled recovery.

A database or object stored on the same host and writable by the same principal as the local registry is not an independent anchor. The repository implements the verification client and protocol contract; deployment and operation of the external anchor service remain infrastructure responsibilities.

## CLI

Pass both `--anchor-url` and `--anchor-public-key` to `scripts/verify_evidence_trust.py`. Supplying only one is an error. Without these options, verification still authenticates the registry signature but does not claim rollback resistance.

## Limits

The anchor protects against local rollback only while the remote authority, its signing key, transport endpoint and durable monotonic state remain trustworthy. Compromise of the anchor service or its signing key can authorize rollback. Registry sequence numbers are not security controls unless the anchor enforces monotonicity independently.
