"""Durable monotonic trust-registry anchor authority (transport-agnostic core)."""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


_GENESIS_HASH = "0" * 64


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class AnchorConflict(ValueError):
    """A publish request violates monotonic head invariants or audit integrity."""


class PublisherUnauthorized(ValueError):
    """Publisher key is not trusted, active, or its request signature is invalid."""


class MonotonicAnchor:
    """SQLite-backed CAS authority; database ownership must be independent of registry host."""

    def __init__(
        self,
        database: Path,
        response_signing_key: Ed25519PrivateKey,
        publishers: Mapping[str, Ed25519PublicKey],
        *,
        publisher_status: Mapping[str, str] | None = None,
    ) -> None:
        self.database = database
        self.response_signing_key = response_signing_key
        self.publishers = dict(publishers)
        self.publisher_status = dict(publisher_status or {key_id: "active" for key_id in publishers})
        if not self.publishers:
            raise ValueError("at least one publisher key must be configured")
        if set(self.publisher_status) != set(self.publishers):
            raise ValueError("publisher status must be configured for every trusted key")
        if any(status not in {"active", "retired", "revoked"} for status in self.publisher_status.values()):
            raise ValueError("publisher status must be active, retired, or revoked")
        database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS anchor_head (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                sequence INTEGER NOT NULL CHECK(sequence > 0),
                registry_sha256 TEXT NOT NULL CHECK(length(registry_sha256) = 64),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS anchor_publish_log (
                request_id TEXT PRIMARY KEY,
                sequence INTEGER NOT NULL,
                registry_sha256 TEXT NOT NULL,
                publisher_key_id TEXT NOT NULL,
                accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(anchor_publish_log)")}
            if "previous_hash" not in columns:
                conn.execute("ALTER TABLE anchor_publish_log ADD COLUMN previous_hash TEXT")
            if "event_hash" not in columns:
                conn.execute("ALTER TABLE anchor_publish_log ADD COLUMN event_hash TEXT")
            self._backfill_audit_chain(conn)
            self._verify_audit_chain(conn)
            conn.execute("""CREATE TRIGGER IF NOT EXISTS anchor_publish_log_no_update
                BEFORE UPDATE ON anchor_publish_log BEGIN
                    SELECT RAISE(ABORT, 'anchor publish log is append-only');
                END""")
            conn.execute("""CREATE TRIGGER IF NOT EXISTS anchor_publish_log_no_delete
                BEFORE DELETE ON anchor_publish_log BEGIN
                    SELECT RAISE(ABORT, 'anchor publish log is append-only');
                END""")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    @staticmethod
    def _event_hash(
        request_id: str, sequence: int, digest: str, publisher_key_id: str,
        accepted_at: str, previous_hash: str,
    ) -> str:
        event = {
            "request_id": request_id,
            "sequence": sequence,
            "registry_sha256": digest,
            "publisher_key_id": publisher_key_id,
            "accepted_at": accepted_at,
            "previous_hash": previous_hash,
        }
        return hashlib.sha256(canonical_json(event)).hexdigest()

    def _backfill_audit_chain(self, conn: sqlite3.Connection) -> None:
        """Upgrade pre-chain rows deterministically, preserving their original timestamps."""
        previous_hash = _GENESIS_HASH
        rows = conn.execute("""SELECT request_id, sequence, registry_sha256, publisher_key_id, accepted_at
            FROM anchor_publish_log ORDER BY sequence, request_id""").fetchall()
        for request_id, sequence, digest, key_id, accepted_at in rows:
            existing = conn.execute(
                "SELECT previous_hash, event_hash FROM anchor_publish_log WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if existing and existing[0] is not None and existing[1] is not None:
                previous_hash = existing[1]
                continue
            event_hash = self._event_hash(request_id, sequence, digest, key_id, accepted_at, previous_hash)
            conn.execute(
                "UPDATE anchor_publish_log SET previous_hash=?, event_hash=? WHERE request_id=?",
                (previous_hash, event_hash, request_id),
            )
            previous_hash = event_hash

    def _verify_audit_chain(self, conn: sqlite3.Connection) -> tuple[int, str]:
        previous_hash = _GENESIS_HASH
        count = 0
        rows = conn.execute("""SELECT request_id, sequence, registry_sha256, publisher_key_id,
            accepted_at, previous_hash, event_hash FROM anchor_publish_log ORDER BY sequence, request_id""")
        for request_id, sequence, digest, key_id, accepted_at, stored_previous, stored_hash in rows:
            expected = self._event_hash(request_id, sequence, digest, key_id, accepted_at, previous_hash)
            if stored_previous != previous_hash or stored_hash != expected:
                raise AnchorConflict("anchor append-only audit chain integrity failure")
            previous_hash = expected
            count += 1
        return count, previous_hash

    def verify_audit_chain(self) -> dict[str, Any]:
        """Verify the local hash chain; export its head to an independent trust domain."""
        with self._connect() as conn:
            count, head_hash = self._verify_audit_chain(conn)
        return {"valid": True, "event_count": count, "head_hash": head_hash}

    def publish(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Authenticate publisher and atomically advance the sequence (strictly greater)."""
        required = {"version", "sequence", "registry_sha256", "request_id", "publisher_key_id", "signature"}
        if set(request) != required or request.get("version") != 1:
            raise AnchorConflict("malformed publish request")
        sequence, digest, request_id, key_id = (
            request.get("sequence"), request.get("registry_sha256"),
            request.get("request_id"), request.get("publisher_key_id"),
        )
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise AnchorConflict("sequence must be a positive integer")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise AnchorConflict("registry_sha256 must be lowercase SHA-256 hex")
        if not isinstance(request_id, str) or not request_id or len(request_id) > 200:
            raise AnchorConflict("request_id must be non-empty and bounded")
        if not isinstance(key_id, str) or key_id not in self.publishers:
            raise PublisherUnauthorized("unknown publisher key")
        if self.publisher_status[key_id] != "active":
            raise PublisherUnauthorized(f"publisher key is {self.publisher_status[key_id]}")
        signed = {k: request[k] for k in ("version", "sequence", "registry_sha256", "request_id", "publisher_key_id")}
        try:
            signature = base64.b64decode(request["signature"], validate=True)
            self.publishers[key_id].verify(signature, canonical_json(signed))
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise PublisherUnauthorized("invalid publisher signature") from exc

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._verify_audit_chain(conn)
            prior = conn.execute("SELECT sequence, registry_sha256 FROM anchor_head WHERE singleton=1").fetchone()
            duplicate = conn.execute("SELECT sequence, registry_sha256 FROM anchor_publish_log WHERE request_id=?", (request_id,)).fetchone()
            if duplicate:
                if duplicate == (sequence, digest):
                    conn.execute("COMMIT")
                    return {"sequence": sequence, "registry_sha256": digest, "idempotent": True}
                raise AnchorConflict("request_id already used for different content")
            if prior and sequence <= prior[0]:
                if sequence == prior[0] and digest == prior[1]:
                    raise AnchorConflict("head already has this sequence; use a fresh higher sequence")
                raise AnchorConflict(f"sequence must exceed current head {prior[0]}")
            cursor = conn.execute("SELECT event_hash FROM anchor_publish_log ORDER BY sequence DESC, request_id DESC LIMIT 1")
            previous_hash_row = cursor.fetchone()
            previous_hash = previous_hash_row[0] if previous_hash_row else _GENESIS_HASH
            accepted_at = conn.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0]
            event_hash = self._event_hash(request_id, sequence, digest, key_id, accepted_at, previous_hash)
            conn.execute("""INSERT INTO anchor_head(singleton,sequence,registry_sha256) VALUES(1,?,?)
                ON CONFLICT(singleton) DO UPDATE SET sequence=excluded.sequence,
                registry_sha256=excluded.registry_sha256, updated_at=CURRENT_TIMESTAMP""", (sequence,digest))
            conn.execute("""INSERT INTO anchor_publish_log
                (request_id,sequence,registry_sha256,publisher_key_id,accepted_at,previous_hash,event_hash)
                VALUES(?,?,?,?,?,?,?)""",
                (request_id,sequence,digest,key_id,accepted_at,previous_hash,event_hash))
            conn.execute("COMMIT")
            return {"sequence": sequence, "registry_sha256": digest, "idempotent": False}
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def signed_head(self, nonce: str) -> dict[str, Any]:
        """Return the Phase-28 response envelope; HTTP adapter must enforce HTTPS/no-store."""
        if not isinstance(nonce, str) or not nonce or len(nonce) > 256:
            raise ValueError("nonce must be non-empty and bounded")
        with self._connect() as conn:
            self._verify_audit_chain(conn)
            row = conn.execute("SELECT sequence, registry_sha256 FROM anchor_head WHERE singleton=1").fetchone()
        if row is None:
            raise LookupError("anchor has no published head")
        payload = {"version": 1, "sequence": row[0], "registry_sha256": row[1], "nonce": nonce}
        signature = self.response_signing_key.sign(canonical_json(payload))
        return {"payload": payload, "signature": base64.b64encode(signature).decode("ascii")}

    @staticmethod
    def registry_digest(registry: Mapping[str, Any]) -> str:
        return hashlib.sha256(canonical_json(registry)).hexdigest()
