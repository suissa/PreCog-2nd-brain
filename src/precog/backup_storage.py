"""Provider-neutral immutable backup archives and retention-aware recovery.

ObjectStore adapters must implement conditional create and enforce retention in
their own storage domain (for example, bucket object-lock/WORM). The in-memory
adapter is for tests only and is not independent durable storage.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol
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


class BackupStorageError(ValueError):
    """An archive, object-store operation, or retention request is invalid."""


@dataclass(frozen=True)
class StoredObject:
    key: str
    data: bytes
    retain_until: datetime


class ObjectStore(Protocol):
    """Minimal adapter contract; implementations must provide durable semantics."""

    def put_if_absent(self, key: str, data: bytes, retain_until: datetime) -> None: ...
    def get(self, key: str) -> StoredObject: ...
    def list(self, prefix: str) -> list[StoredObject]: ...
    def delete(self, key: str, *, now: datetime) -> None: ...


class InMemoryObjectStore:
    """Deterministic test adapter. Never use as production backup storage."""

    def __init__(self) -> None:
        self._objects: dict[str, StoredObject] = {}

    def put_if_absent(self, key: str, data: bytes, retain_until: datetime) -> None:
        prior = self._objects.get(key)
        item = StoredObject(key, bytes(data), retain_until)
        if prior is not None:
            if prior != item:
                raise BackupStorageError("immutable object key already contains different data")
            return
        self._objects[key] = item

    def get(self, key: str) -> StoredObject:
        try:
            return self._objects[key]
        except KeyError as exc:
            raise BackupStorageError("archive object is unavailable") from exc

    def list(self, prefix: str) -> list[StoredObject]:
        return sorted(
            (item for key, item in self._objects.items() if key.startswith(prefix)),
            key=lambda item: item.key,
        )

    def delete(self, key: str, *, now: datetime) -> None:
        item = self.get(key)
        _aware_utc(now, "now")
        if now < item.retain_until:
            raise BackupStorageError("object is protected by its retention period")
        del self._objects[key]


def _aware_utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BackupStorageError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise BackupStorageError("archive data is not canonical JSON") from exc


def _verify_sqlite(path: Path) -> None:
    try:
        with sqlite3.connect(path) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupStorageError("backup database integrity check failed") from exc
    if result is None or result[0] != "ok":
        raise BackupStorageError("backup database integrity check failed")


def _sign(payload: dict[str, Any], key: Ed25519PrivateKey, key_id: str) -> dict[str, Any]:
    return {
        "key_id": key_id,
        "payload": payload,
        "signature": base64.b64encode(key.sign(_json_bytes(payload))).decode("ascii"),
    }


def archive_recovery_backup(
    source_database: Path,
    checkpoint: Mapping[str, Any],
    recovery_trusted_keys: Mapping[str, Ed25519PublicKey],
    store: ObjectStore,
    *,
    expected_authority_id: str,
    response_signing_key: Ed25519PrivateKey,
    publishers: Mapping[str, Ed25519PublicKey],
    manifest_signing_key: Ed25519PrivateKey,
    manifest_key_id: str,
    retain_until: datetime,
    publisher_status: Mapping[str, str] | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Create, verify, and immutably archive a backup plus its external checkpoint."""
    if not expected_authority_id or len(expected_authority_id) > 200:
        raise BackupStorageError("expected_authority_id must be non-empty and bounded")
    if not manifest_key_id or len(manifest_key_id) > 128 or not publishers:
        raise BackupStorageError("manifest key ID and publisher keys are required")
    retention = _aware_utc(retain_until, "retain_until")
    created = _aware_utc(created_at or datetime.now(timezone.utc), "created_at")
    if retention <= created:
        raise BackupStorageError("retain_until must be later than archive creation")
    source = Path(source_database)
    if not source.is_file():
        raise BackupStorageError("source database is unavailable")

    with tempfile.TemporaryDirectory(prefix="precog-archive-") as temp:
        snapshot = Path(temp) / "snapshot.sqlite3"
        source_uri = "file:" + quote(str(source.resolve())) + "?mode=ro"
        try:
            with sqlite3.connect(source_uri, uri=True, timeout=10) as source_conn:
                with sqlite3.connect(snapshot) as target_conn:
                    source_conn.backup(target_conn)
        except sqlite3.Error as exc:
            raise BackupStorageError("consistent backup capture failed") from exc
        _verify_sqlite(snapshot)

        # Validate the independent checkpoint against the exact captured snapshot,
        # not against a separately sampled live source state.
        restored = MonotonicAnchor(
            snapshot, response_signing_key, publishers,
            publisher_status=publisher_status,
        )
        try:
            state = verify_recovery_checkpoint(
                checkpoint, recovery_trusted_keys, restored,
                expected_authority_id=expected_authority_id,
            )
        except RecoveryCheckpointError as exc:
            raise BackupStorageError("checkpoint does not authenticate captured backup") from exc
        backup_data = snapshot.read_bytes()

    checkpoint_data = _json_bytes(checkpoint)
    backup_hash = _digest(backup_data)
    checkpoint_hash = _digest(checkpoint_data)
    backup_key = f"precog/v1/{expected_authority_id}/backup/sha256/{backup_hash}"
    checkpoint_key = f"precog/v1/{expected_authority_id}/checkpoint/sha256/{checkpoint_hash}"
    payload: dict[str, Any] = {
        "version": 1,
        "authority_id": expected_authority_id,
        "created_at": created.isoformat(),
        "retain_until": retention.isoformat(),
        "sequence": state["sequence"],
        "backup_key": backup_key,
        "backup_sha256": backup_hash,
        "backup_size": len(backup_data),
        "checkpoint_key": checkpoint_key,
        "checkpoint_sha256": checkpoint_hash,
    }
    manifest = _sign(payload, manifest_signing_key, manifest_key_id)
    manifest_data = _json_bytes(manifest)
    manifest_hash = _digest(manifest_data)
    manifest_key = f"precog/v1/{expected_authority_id}/manifest/sha256/{manifest_hash}"

    # Publish data objects first and the signed manifest last. A partial upload
    # leaves unreferenced immutable objects, never a manifest pointing at missing data.
    store.put_if_absent(backup_key, backup_data, retention)
    store.put_if_absent(checkpoint_key, checkpoint_data, retention)
    store.put_if_absent(manifest_key, manifest_data, retention)
    return {"manifest": manifest, "manifest_key": manifest_key, "manifest_sha256": manifest_hash}


def verify_archive_manifest(
    manifest: Mapping[str, Any],
    trusted_manifest_keys: Mapping[str, Ed25519PublicKey],
    *,
    expected_authority_id: str,
) -> dict[str, Any]:
    if set(manifest) != {"key_id", "payload", "signature"}:
        raise BackupStorageError("malformed archive manifest envelope")
    key_id, payload, signature_text = (
        manifest.get("key_id"), manifest.get("payload"), manifest.get("signature")
    )
    required = {
        "version", "authority_id", "created_at", "retain_until", "sequence",
        "backup_key", "backup_sha256", "backup_size", "checkpoint_key",
        "checkpoint_sha256",
    }
    if (
        not isinstance(key_id, str) or key_id not in trusted_manifest_keys
        or not isinstance(payload, dict) or set(payload) != required
        or payload.get("version") != 1
        or payload.get("authority_id") != expected_authority_id
        or not isinstance(signature_text, str)
    ):
        raise BackupStorageError("untrusted or malformed archive manifest")
    try:
        signature = base64.b64decode(signature_text, validate=True)
        trusted_manifest_keys[key_id].verify(signature, _json_bytes(payload))
    except (InvalidSignature, ValueError, TypeError, binascii.Error) as exc:
        raise BackupStorageError("invalid archive manifest signature") from exc

    try:
        created = _aware_utc(datetime.fromisoformat(payload["created_at"]), "created_at")
        retention = _aware_utc(datetime.fromisoformat(payload["retain_until"]), "retain_until")
    except (TypeError, ValueError, KeyError) as exc:
        raise BackupStorageError("invalid archive timestamps") from exc
    if retention <= created:
        raise BackupStorageError("archive retention interval is invalid")
    for field in ("backup_sha256", "checkpoint_sha256"):
        value = payload.get(field)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise BackupStorageError("invalid archive content digest")
    expected_backup_key = f"precog/v1/{expected_authority_id}/backup/sha256/{payload['backup_sha256']}"
    expected_checkpoint_key = f"precog/v1/{expected_authority_id}/checkpoint/sha256/{payload['checkpoint_sha256']}"
    if payload.get("backup_key") != expected_backup_key or payload.get("checkpoint_key") != expected_checkpoint_key:
        raise BackupStorageError("archive object key does not match signed content digest")
    size = payload.get("backup_size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise BackupStorageError("invalid backup size")
    sequence = payload.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise BackupStorageError("invalid backup sequence")
    return dict(payload)


def restore_archived_backup(
    manifest: Mapping[str, Any],
    store: ObjectStore,
    trusted_manifest_keys: Mapping[str, Ed25519PublicKey],
    recovery_trusted_keys: Mapping[str, Ed25519PublicKey],
    target_database: Path,
    *,
    expected_authority_id: str,
    response_signing_key: Ed25519PrivateKey,
    publishers: Mapping[str, Ed25519PublicKey],
    publisher_status: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Verify every archived byte and checkpoint before atomically exposing a restore."""
    payload = verify_archive_manifest(
        manifest, trusted_manifest_keys, expected_authority_id=expected_authority_id
    )
    backup_obj = store.get(payload["backup_key"])
    checkpoint_obj = store.get(payload["checkpoint_key"])
    for item in (backup_obj, checkpoint_obj):
        if _aware_utc(item.retain_until, "object retain_until") < _aware_utc(
            datetime.fromisoformat(payload["retain_until"]), "manifest retain_until"
        ):
            raise BackupStorageError("storage retention is shorter than signed manifest retention")
    if _digest(backup_obj.data) != payload["backup_sha256"] or len(backup_obj.data) != payload["backup_size"]:
        raise BackupStorageError("archived backup digest or size mismatch")
    if _digest(checkpoint_obj.data) != payload["checkpoint_sha256"]:
        raise BackupStorageError("archived checkpoint digest mismatch")
    try:
        checkpoint = json.loads(checkpoint_obj.data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupStorageError("archived checkpoint is malformed") from exc
    if not isinstance(checkpoint, dict):
        raise BackupStorageError("archived checkpoint is malformed")

    target = Path(target_database)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise BackupStorageError("restore target already exists")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".precog-restore-", suffix=".sqlite3", dir=target.parent, delete=False
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(backup_obj.data)
            stream.flush()
            os.fsync(stream.fileno())
        _verify_sqlite(temp_path)
        authority = MonotonicAnchor(
            temp_path, response_signing_key, publishers,
            publisher_status=publisher_status,
        )
        state = verify_recovery_checkpoint(
            checkpoint, recovery_trusted_keys, authority,
            expected_authority_id=expected_authority_id,
        )
        if state["sequence"] != payload["sequence"]:
            raise BackupStorageError("restored sequence differs from signed archive manifest")
        os.replace(temp_path, target)
        temp_path = None
        return {"restored": True, "authority_id": expected_authority_id, **state}
    except (RecoveryCheckpointError, sqlite3.Error, OSError) as exc:
        raise BackupStorageError("archived backup restore verification failed") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def list_archived_manifests(
    store: ObjectStore,
    trusted_manifest_keys: Mapping[str, Ed25519PublicKey],
    *,
    authority_id: str,
) -> list[dict[str, Any]]:
    """Return verified manifests newest-first; ignore no malformed signed entries."""
    prefix = f"precog/v1/{authority_id}/manifest/sha256/"
    manifests: list[dict[str, Any]] = []
    for item in store.list(prefix):
        if _digest(item.data) != item.key.rsplit("/", 1)[-1]:
            raise BackupStorageError("stored manifest content digest mismatch")
        try:
            envelope = json.loads(item.data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackupStorageError("stored manifest is malformed") from exc
        if not isinstance(envelope, dict):
            raise BackupStorageError("stored manifest is malformed")
        payload = verify_archive_manifest(
            envelope, trusted_manifest_keys, expected_authority_id=authority_id
        )
        manifests.append({"manifest": envelope, "payload": payload, "manifest_key": item.key})
    return sorted(manifests, key=lambda item: item["payload"]["created_at"], reverse=True)


def prune_expired_objects(
    store: ObjectStore,
    *,
    prefix: str,
    now: datetime | None = None,
) -> list[str]:
    """Delete only objects whose retention deadline has elapsed; backend must enforce it too."""
    instant = _aware_utc(now or datetime.now(timezone.utc), "now")
    deleted: list[str] = []
    for item in store.list(prefix):
        if instant >= _aware_utc(item.retain_until, "retain_until"):
            store.delete(item.key, now=instant)
            deleted.append(item.key)
    return deleted
