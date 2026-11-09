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
