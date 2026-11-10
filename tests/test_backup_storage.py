import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.anchor_recovery import create_recovery_checkpoint
from precog.anchor_service import MonotonicAnchor, canonical_json
from precog.backup_storage import (
    BackupStorageError,
    InMemoryObjectStore,
    archive_recovery_backup,
    list_archived_manifests,
    prune_expired_objects,
    restore_archived_backup,
    verify_archive_manifest,
)


def signed_publish(key, sequence, digest, request_id):
    payload = {
        "version": 1,
        "sequence": sequence,
        "registry_sha256": digest,
        "request_id": request_id,
        "publisher_key_id": "publisher",
    }
    return {
        **payload,
        "signature": base64.b64encode(key.sign(canonical_json(payload))).decode(),
    }


def setup_anchor(path: Path):
    publisher = Ed25519PrivateKey.generate()
    response = Ed25519PrivateKey.generate()
    recovery = Ed25519PrivateKey.generate()
    manifest = Ed25519PrivateKey.generate()
    authority = MonotonicAnchor(path, response, {"publisher": publisher.public_key()})
    authority.publish(signed_publish(publisher, 1, "a" * 64, "first"))
    checkpoint = create_recovery_checkpoint(
        authority, recovery, key_id="recovery", authority_id="anchor-prod"
    )
    return authority, publisher, response, recovery, manifest, checkpoint


def archive(path, checkpoint, publisher, response, recovery, manifest_key, store, retain_until):
    return archive_recovery_backup(
        path, checkpoint, {"recovery": recovery.public_key()}, store,
        expected_authority_id="anchor-prod",
        response_signing_key=response,
        publishers={"publisher": publisher.public_key()},
        manifest_signing_key=manifest_key,
        manifest_key_id="archive-manifest",
        retain_until=retain_until,
    )


def test_archive_restore_round_trip_and_signed_manifest(tmp_path):
    source = tmp_path / "anchor.db"
    _, publisher, response, recovery, manifest_key, checkpoint = setup_anchor(source)
    store = InMemoryObjectStore()
    archived = archive(
        source, checkpoint, publisher, response, recovery, manifest_key, store,
        datetime.now(timezone.utc) + timedelta(days=30),
    )
    payload = verify_archive_manifest(
        archived["manifest"], {"archive-manifest": manifest_key.public_key()},
        expected_authority_id="anchor-prod",
    )
    assert payload["sequence"] == 1
    assert len(payload["backup_sha256"]) == 64
    history = list_archived_manifests(
        store, {"archive-manifest": manifest_key.public_key()}, authority_id="anchor-prod"
    )
    assert len(history) == 1

    target = tmp_path / "restored.db"
    result = restore_archived_backup(
        archived["manifest"], store,
        {"archive-manifest": manifest_key.public_key()},
        {"recovery": recovery.public_key()}, target,
        expected_authority_id="anchor-prod",
        response_signing_key=response,
        publishers={"publisher": publisher.public_key()},
    )
    assert result["restored"] is True
    assert result["sequence"] == 1
    assert target.is_file()


def test_archive_refuses_checkpoint_that_does_not_match_snapshot(tmp_path):
    source = tmp_path / "anchor.db"
    authority, publisher, response, recovery, manifest_key, checkpoint = setup_anchor(source)
    authority.publish(signed_publish(publisher, 2, "b" * 64, "second"))
    with pytest.raises(BackupStorageError, match="checkpoint"):
        archive(
            source, checkpoint, publisher, response, recovery, manifest_key,
            InMemoryObjectStore(), datetime.now(timezone.utc) + timedelta(days=1),
        )


def test_restore_fails_closed_on_backup_object_tampering(tmp_path):
    source = tmp_path / "anchor.db"
    _, publisher, response, recovery, manifest_key, checkpoint = setup_anchor(source)
    store = InMemoryObjectStore()
    archived = archive(
        source, checkpoint, publisher, response, recovery, manifest_key, store,
        datetime.now(timezone.utc) + timedelta(days=1),
    )
    backup_key = archived["manifest"]["payload"]["backup_key"]
    original = store.get(backup_key)
    store._objects[backup_key] = type(original)(
        original.key, original.data + b"tampered", original.retain_until
    )
    with pytest.raises(BackupStorageError, match="digest"):
        restore_archived_backup(
            archived["manifest"], store,
            {"archive-manifest": manifest_key.public_key()},
            {"recovery": recovery.public_key()}, tmp_path / "bad.db",
            expected_authority_id="anchor-prod",
            response_signing_key=response,
            publishers={"publisher": publisher.public_key()},
        )
    assert not (tmp_path / "bad.db").exists()


def test_retention_blocks_early_delete_and_prunes_only_expired_objects():
    store = InMemoryObjectStore()
    now = datetime.now(timezone.utc)
    store.put_if_absent("keep", b"retained", now + timedelta(days=2))
    store.put_if_absent("expired", b"expired", now - timedelta(seconds=1))
    with pytest.raises(BackupStorageError, match="retention"):
        store.delete("keep", now=now)
    deleted = prune_expired_objects(store, prefix="", now=now)
    assert deleted == ["expired"]
    assert store.get("keep").data == b"retained"


def test_manifest_signature_tampering_is_rejected(tmp_path):
    source = tmp_path / "anchor.db"
    _, publisher, response, recovery, manifest_key, checkpoint = setup_anchor(source)
    archived = archive(
        source, checkpoint, publisher, response, recovery, manifest_key,
        InMemoryObjectStore(), datetime.now(timezone.utc) + timedelta(days=1),
    )
    archived["manifest"]["payload"]["sequence"] = 99
    with pytest.raises(BackupStorageError, match="signature"):
        verify_archive_manifest(
            archived["manifest"], {"archive-manifest": manifest_key.public_key()},
            expected_authority_id="anchor-prod",
        )


def test_retention_deadline_must_be_timezone_aware_and_future(tmp_path):
    source = tmp_path / "anchor.db"
    _, publisher, response, recovery, manifest_key, checkpoint = setup_anchor(source)
    with pytest.raises(BackupStorageError, match="timezone"):
        archive(
            source, checkpoint, publisher, response, recovery, manifest_key,
            InMemoryObjectStore(), datetime.now(),
        )
    with pytest.raises(BackupStorageError, match="later"):
        archive(
            source, checkpoint, publisher, response, recovery, manifest_key,
            InMemoryObjectStore(), datetime.now(timezone.utc) - timedelta(seconds=1),
        )
