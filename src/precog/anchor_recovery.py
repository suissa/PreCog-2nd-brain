"""Signed recovery checkpoints for detecting stale or divergent anchor restores.

The checkpoint must be retained outside the anchor host and signed by an
independent recovery key. It is deliberately separate from the online response
signing key and publisher keys.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from precog.anchor_service import MonotonicAnchor, canonical_json


class RecoveryCheckpointError(ValueError):
    """A recovery checkpoint is malformed, untrusted, or does not match state."""


def _current_state(authority: MonotonicAnchor) -> dict[str, Any]:
    conn = authority._connect()
    try:
        # Pin all reads to one SQLite snapshot so a concurrent publish cannot
        # produce a checkpoint assembled from two different authority states.
        conn.execute("BEGIN")
        count, audit_head = authority._verify_audit_chain(conn)
        head = conn.execute(
            "SELECT sequence, registry_sha256 FROM anchor_head WHERE singleton=1"
        ).fetchone()
        last = conn.execute(
            """SELECT sequence, registry_sha256 FROM anchor_publish_log
               ORDER BY sequence DESC, request_id DESC LIMIT 1"""
        ).fetchone()
        if head is None:
            if count or last is not None:
                raise RecoveryCheckpointError("anchor head missing while audit receipts exist")
            sequence, digest = 0, None
        else:
            sequence, digest = head
            if last != (sequence, digest):
                raise RecoveryCheckpointError("anchor head diverges from verified audit receipts")
        conn.execute("COMMIT")
        return {
            "sequence": sequence,
            "registry_sha256": digest,
            "audit_event_count": count,
            "audit_head_hash": audit_head,
        }
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def create_recovery_checkpoint(
    authority: MonotonicAnchor,
    signing_key: Ed25519PrivateKey,
    *,
    key_id: str,
    authority_id: str,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a signed snapshot; store the result in an independent trust domain."""
    if not key_id or len(key_id) > 128 or not authority_id or len(authority_id) > 200:
        raise RecoveryCheckpointError("key_id and authority_id must be non-empty and bounded")
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise RecoveryCheckpointError("created_at must be timezone-aware")
    payload = {
        "version": 1,
        "key_id": key_id,
        "authority_id": authority_id,
        **_current_state(authority),
        "created_at": timestamp.astimezone(timezone.utc).isoformat(),
    }
    signature = signing_key.sign(canonical_json(payload))
    return {
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def verify_recovery_checkpoint(
    checkpoint: Mapping[str, Any],
    trusted_keys: Mapping[str, Ed25519PublicKey],
    authority: MonotonicAnchor,
    *,
    expected_authority_id: str,
) -> dict[str, Any]:
    """Authenticate an external checkpoint and require exact restored-state equality."""
    if set(checkpoint) != {"payload", "signature"}:
        raise RecoveryCheckpointError("malformed recovery checkpoint envelope")
    payload = checkpoint.get("payload")
    signature_text = checkpoint.get("signature")
    required = {
        "version", "key_id", "authority_id", "sequence", "registry_sha256",
        "audit_event_count", "audit_head_hash", "created_at",
    }
    if not isinstance(payload, dict) or set(payload) != required or payload.get("version") != 1:
        raise RecoveryCheckpointError("malformed recovery checkpoint payload")
    key_id = payload.get("key_id")
    if not isinstance(key_id, str) or key_id not in trusted_keys:
        raise RecoveryCheckpointError("unknown recovery signing key")
    if payload.get("authority_id") != expected_authority_id:
        raise RecoveryCheckpointError("recovery checkpoint belongs to another authority")
    if not isinstance(signature_text, str):
        raise RecoveryCheckpointError("missing recovery checkpoint signature")
    try:
        signature = base64.b64decode(signature_text, validate=True)
        trusted_keys[key_id].verify(signature, canonical_json(payload))
    except (InvalidSignature, ValueError, TypeError, binascii.Error) as exc:
        raise RecoveryCheckpointError("invalid recovery checkpoint signature") from exc
    timestamp = payload.get("created_at")
    if not isinstance(timestamp, str):
        raise RecoveryCheckpointError("invalid recovery checkpoint timestamp")
    try:
        parsed = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError) as exc:
        raise RecoveryCheckpointError("invalid recovery checkpoint timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RecoveryCheckpointError("recovery checkpoint timestamp must include timezone")
    state = _current_state(authority)
    expected = {
        "sequence": payload.get("sequence"),
        "registry_sha256": payload.get("registry_sha256"),
        "audit_event_count": payload.get("audit_event_count"),
        "audit_head_hash": payload.get("audit_head_hash"),
    }
    if expected != state:
        raise RecoveryCheckpointError("restored anchor does not match independent recovery checkpoint")
    return {"valid": True, **state, "authority_id": expected_authority_id, "key_id": key_id}
