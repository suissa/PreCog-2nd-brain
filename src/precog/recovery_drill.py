"""Isolated, signed backup/restore drills for the monotonic anchor authority.

The drill never writes to the source database. It uses SQLite's online backup API,
verifies the copied database, restores into a temporary directory, and compares
that restored state with an independently retained recovery checkpoint.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from precog.anchor_recovery import (
    RecoveryCheckpointError,
    verify_recovery_checkpoint,
)
from precog.anchor_service import MonotonicAnchor, canonical_json


class RecoveryDrillError(ValueError):
    """A recovery drill request or signed evidence is invalid."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checkpoint_digest(checkpoint: Mapping[str, Any] | None) -> str | None:
    if checkpoint is None:
        return None
    try:
        return hashlib.sha256(canonical_json(checkpoint)).hexdigest()
    except (TypeError, ValueError) as exc:
        raise RecoveryDrillError("checkpoint is not canonical JSON data") from exc


def _integrity_check(database: Path) -> None:
    with sqlite3.connect(database) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()
    if result is None or result[0] != "ok":
        raise RecoveryDrillError("restored database integrity check failed")


def _sign_evidence(
    payload: dict[str, Any],
    signing_key: Ed25519PrivateKey,
    key_id: str,
) -> dict[str, Any]:
    signed = {"payload": payload, "signature": base64.b64encode(
        signing_key.sign(canonical_json(payload))
    ).decode("ascii")}
    return {"key_id": key_id, **signed}


def run_recovery_drill(
    source_database: Path,
    checkpoint: Mapping[str, Any] | None,
    recovery_trusted_keys: Mapping[str, Ed25519PublicKey],
    *,
    expected_authority_id: str,
    response_signing_key: Ed25519PrivateKey,
    publishers: Mapping[str, Ed25519PublicKey],
    evidence_signing_key: Ed25519PrivateKey,
    evidence_key_id: str,
    publisher_status: Mapping[str, str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run a read-only-source backup/restore drill and return signed evidence.

    The evidence signing key must be distinct from recovery, publisher, and
    online response keys. Key separation is enforced by caller provisioning:
    Ed25519 private-key objects cannot be safely compared by identity across
    independently loaded instances.
    """
    if not expected_authority_id or len(expected_authority_id) > 200:
        raise RecoveryDrillError("expected_authority_id must be non-empty and bounded")
    if not evidence_key_id or len(evidence_key_id) > 128:
        raise RecoveryDrillError("evidence_key_id must be non-empty and bounded")
    if not publishers:
        raise RecoveryDrillError("at least one publisher key is required")
    identifier = run_id or str(uuid.uuid4())
    if not isinstance(identifier, str) or not identifier or len(identifier) > 200:
        raise RecoveryDrillError("run_id must be non-empty and bounded")

    started_at = datetime.now(timezone.utc).isoformat()
    checkpoint_hash = _checkpoint_digest(checkpoint)
    backup_hash: str | None = None
    restored_state: dict[str, Any] | None = None
    status = "failed"
    reason = "checkpoint_unavailable"

    if checkpoint is not None:
        try:
            source = Path(source_database)
            if not source.is_file():
                reason = "source_database_unavailable"
                raise RecoveryDrillError(reason)
            with tempfile.TemporaryDirectory(prefix="precog-recovery-drill-") as temp:
                backup_path = Path(temp) / "anchor-backup.sqlite3"
                restored_path = Path(temp) / "anchor-restored.sqlite3"
                # Read-only URI prevents accidental source mutations; backup()
                # captures a transactionally consistent SQLite snapshot.
                source_uri = "file:" + quote(str(source.resolve())) + "?mode=ro"
                with sqlite3.connect(source_uri, uri=True, timeout=10) as source_conn:
                    with sqlite3.connect(backup_path) as backup_conn:
                        source_conn.backup(backup_conn)
                backup_hash = _sha256_file(backup_path)
                _integrity_check(backup_path)

                # A second SQLite backup models restore into a fresh target and
                # ensures the verification target is independent of the source.
                with sqlite3.connect(backup_path) as backup_conn:
                    with sqlite3.connect(restored_path) as restored_conn:
                        backup_conn.backup(restored_conn)
                _integrity_check(restored_path)

                restored = MonotonicAnchor(
                    restored_path,
                    response_signing_key,
                    publishers,
                    publisher_status=publisher_status,
                )
                restored_state = verify_recovery_checkpoint(
                    checkpoint,
                    recovery_trusted_keys,
                    restored,
                    expected_authority_id=expected_authority_id,
                )
                status = "passed"
                reason = "verified"
        except RecoveryCheckpointError:
            reason = "checkpoint_mismatch_or_untrusted"
        except (OSError, sqlite3.Error, RecoveryDrillError, ValueError):
            # Do not leak database paths, SQL details, key material, or registry data.
            if reason not in {"source_database_unavailable"}:
                reason = "backup_or_restore_failed"

    completed_at = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "version": 1,
        "run_id": identifier,
        "authority_id": expected_authority_id,
        "status": status,
        "reason": reason,
        "checkpoint_sha256": checkpoint_hash,
        "backup_sha256": backup_hash,
        "restored_state": restored_state,
        "started_at": started_at,
        "completed_at": completed_at,
    }
    return _sign_evidence(payload, evidence_signing_key, evidence_key_id)


def verify_recovery_drill_evidence(
    evidence: Mapping[str, Any],
    trusted_evidence_keys: Mapping[str, Ed25519PublicKey],
    *,
    expected_authority_id: str,
) -> dict[str, Any]:
    """Authenticate a drill report; a valid signature does not imply it passed."""
    if set(evidence) != {"key_id", "payload", "signature"}:
        raise RecoveryDrillError("malformed recovery drill evidence envelope")
    key_id = evidence.get("key_id")
    payload = evidence.get("payload")
    signature_text = evidence.get("signature")
    required = {
        "version", "run_id", "authority_id", "status", "reason",
        "checkpoint_sha256", "backup_sha256", "restored_state",
        "started_at", "completed_at",
    }
    if (
        not isinstance(key_id, str)
        or key_id not in trusted_evidence_keys
        or not isinstance(payload, dict)
        or set(payload) != required
        or payload.get("version") != 1
        or payload.get("authority_id") != expected_authority_id
        or payload.get("status") not in {"passed", "failed"}
        or not isinstance(signature_text, str)
    ):
        raise RecoveryDrillError("untrusted or malformed recovery drill evidence")
    try:
        signature = base64.b64decode(signature_text, validate=True)
        trusted_evidence_keys[key_id].verify(signature, canonical_json(payload))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise RecoveryDrillError("invalid recovery drill evidence signature") from exc
    return {"valid": True, "passed": payload["status"] == "passed", "run_id": payload["run_id"]}
