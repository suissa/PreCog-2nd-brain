# Phase 29 — External Monotonic Anchor Authority

This phase implements the durable authority core, not a publicly deployed HTTP service. Deploy its database, process, network adapter and signing keys in an administrative/security domain independent of both registry publisher and verifier hosts.

## Core API

`precog.anchor_service.MonotonicAnchor` provides:
- SQLite durable head and append-only publish receipt table (WAL + FULL synchronous writes).
- Ed25519-authenticated publisher requests, keyed by independently provisioned publisher key ID.
- `publish()`: transaction uses `BEGIN IMMEDIATE`, unique request IDs and strictly increasing sequence; lower sequence, conflicting digest, replayed request ID with changed content and unknown/invalid publisher signatures are rejected.
- `signed_head(nonce)`: Phase 28-compatible signed payload using a distinct anchor response key.
- `registry_digest()`: SHA-256 over canonical JSON (sorted keys, compact separators, UTF-8).

## Publish request

Signed canonical fields: `version=1`, `sequence`, `registry_sha256`, `request_id`, `publisher_key_id`; signature is base64 Ed25519. Transport adapter should expose authenticated `POST /v1/trust-registry/checkpoints` and read-only `GET /v1/trust-registry/head?nonce=...`, enforce TLS, body limits, rate limits, no-store and structured audit logging. The adapter must never trust publisher identity supplied without signature verification.

## Operational constraints

- Keep the SQLite file and backup/restore authority outside the registry host and publisher's write principal; restrict service account and filesystem permissions.
- Provision publisher public keys and anchor response private key out-of-band; do not reuse registry root or evidence signer keys.
- Restore must be operator-approved and prove sequence does not regress (e.g. compare against independent retained head); SQLite backup alone cannot prevent malicious rollback.
- SQLite serializes writers with `BEGIN IMMEDIATE`; race tests cover concurrent sequence submissions. A production multi-replica service must use a shared database with equivalent serializable/CAS semantics, not per-replica SQLite.
- No HTTP server, deployment, key generation, key storage, mTLS configuration or operational SLO is included. Phase 29 supplies tested authority primitives and protocol contract only.


## HTTP transport (Phase 30)

`precog.anchor_http.AnchorWSGIApp` exposes the authority through a WSGI-compatible adapter:
- `GET /v1/trust-registry/head?nonce=...` returns the signed Phase-28 envelope.
- `POST /v1/trust-registry/checkpoints` accepts the Ed25519-authenticated publish request.
- Requires exactly one nonce, JSON content type, bounded 16 KiB request body and complete Content-Length.
- Uses explicit HTTP status mapping for malformed requests, unauthorized publishers, monotonic conflicts and uninitialized authority.
- Responses set `Cache-Control: no-store`, `Pragma: no-cache` and `X-Content-Type-Options: nosniff`.

By default the adapter requires WSGI `wsgi.url_scheme=https`. A TLS-terminating reverse proxy must be the only network ingress and must set the WSGI scheme from its authenticated TLS connection; do not trust arbitrary client-supplied forwarding headers. The adapter does not itself terminate TLS, implement mTLS, provision keys, provide rate limiting or deploy a WSGI server. Configure those at the trusted ingress/runtime boundary. Publisher signatures remain mandatory even behind the proxy.


## Operational hardening (Phase 31)

The authority now maintains a SHA-256 hash chain over accepted publish receipts. Each event binds the request ID, sequence, registry digest, publisher key ID, acceptance timestamp and previous event hash. Startup migrates legacy rows into a deterministic chain, then verifies the full chain. Publish transactions and signed-head reads verify it again and fail closed on a mismatch. SQLite triggers reject ordinary UPDATE and DELETE operations against the receipt log.

Call `verify_audit_chain()` during operational checks and retain its `head_hash` outside the authority host. The local chain is tamper-evident, not independently immutable: an administrator able to rewrite the database and recompute the chain can replace it. The externally retained head (or Phase-28/29 independent anchor) is required to detect a fully rewritten or restored older database. Do not treat SQLite WAL/FULL as protection against host-level rollback.

Publisher key lifecycle is configured with the `publisher_status` mapping:
- `active`: accepted for new checkpoint publications.
- `retired`: retained as trusted historical identity but cannot publish new checkpoints.
- `revoked`: rejected for new publications following compromise or loss of trust.

Rotation is performed by provisioning the replacement public key under a new key ID, marking it active, and retaining the prior public key as retired. A compromised key is marked revoked. The response-signing key remains a separate trust domain and requires its own out-of-band rotation and verifier pin update; this phase does not implement private-key storage or automated rotation.

Operational recovery must compare the restored database's verified audit head and signed monotonic head against an independently retained value before serving traffic. If the independent anchor is unavailable, restoration must remain quarantined rather than silently accepting a potentially stale local backup. No production deployment, independent backup service, mTLS ingress, key vault or disaster-recovery execution is claimed by this repository.
