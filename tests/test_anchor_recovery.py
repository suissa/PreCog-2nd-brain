from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.anchor_recovery import (
    RecoveryCheckpointError,
    create_recovery_checkpoint,
    verify_recovery_checkpoint,
)
from precog.anchor_service import MonotonicAnchor

import base64

from precog.anchor_service import canonical_json


def signed_publish(key, sequence, digest, request_id, key_id):
    payload = {"version": 1, "sequence": sequence, "registry_sha256": digest,
               "request_id": request_id, "publisher_key_id": key_id}
    return {**payload, "signature": base64.b64encode(key.sign(canonical_json(payload))).decode()}


def test_recovery_checkpoint_matches_restored_state(tmp_path):
    publisher = Ed25519PrivateKey.generate()
    response = Ed25519PrivateKey.generate()
    recovery = Ed25519PrivateKey.generate()
    authority = MonotonicAnchor(tmp_path / "anchor.db", response, {"publisher": publisher.public_key()})
    authority.publish(signed_publish(publisher, 1, "a" * 64, "first", "publisher"))
    checkpoint = create_recovery_checkpoint(
        authority, recovery, key_id="recovery-2026", authority_id="anchor-prod",
        created_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
    )
    result = verify_recovery_checkpoint(
        checkpoint, {"recovery-2026": recovery.public_key()}, authority,
        expected_authority_id="anchor-prod",
    )
    assert result["valid"] is True
    assert result["sequence"] == 1


def test_recovery_checkpoint_rejects_rollback(tmp_path):
    publisher = Ed25519PrivateKey.generate()
    response = Ed25519PrivateKey.generate()
    recovery = Ed25519PrivateKey.generate()
    database = tmp_path / "anchor.db"
    authority = MonotonicAnchor(database, response, {"publisher": publisher.public_key()})
    authority.publish(signed_publish(publisher, 1, "a" * 64, "first", "publisher"))
    checkpoint = create_recovery_checkpoint(authority, recovery, key_id="recovery", authority_id="prod")
    authority.publish(signed_publish(publisher, 2, "b" * 64, "second", "publisher"))
    with pytest.raises(RecoveryCheckpointError, match="does not match"):
        verify_recovery_checkpoint(
            checkpoint, {"recovery": recovery.public_key()}, authority,
            expected_authority_id="prod",
        )


def test_recovery_checkpoint_rejects_wrong_key_and_authority(tmp_path):
    response = Ed25519PrivateKey.generate()
    recovery = Ed25519PrivateKey.generate()
    authority = MonotonicAnchor(tmp_path / "anchor.db", response, {"publisher": Ed25519PrivateKey.generate().public_key()})
    checkpoint = create_recovery_checkpoint(authority, recovery, key_id="recovery", authority_id="prod")
    with pytest.raises(RecoveryCheckpointError, match="unknown"):
        verify_recovery_checkpoint(checkpoint, {}, authority, expected_authority_id="prod")
    with pytest.raises(RecoveryCheckpointError, match="another authority"):
        verify_recovery_checkpoint(
            checkpoint, {"recovery": recovery.public_key()}, authority,
            expected_authority_id="staging",
        )


def test_recovery_checkpoint_rejects_tampering(tmp_path):
    response = Ed25519PrivateKey.generate()
    recovery = Ed25519PrivateKey.generate()
    authority = MonotonicAnchor(tmp_path / "anchor.db", response, {"publisher": Ed25519PrivateKey.generate().public_key()})
    checkpoint = create_recovery_checkpoint(authority, recovery, key_id="recovery", authority_id="prod")
    checkpoint["payload"]["audit_event_count"] = 9
    with pytest.raises(RecoveryCheckpointError, match="signature"):
        verify_recovery_checkpoint(
            checkpoint, {"recovery": recovery.public_key()}, authority,
            expected_authority_id="prod",
        )


def test_recovery_checkpoint_requires_timezone_aware_time(tmp_path):
    authority = MonotonicAnchor(
        tmp_path / "anchor.db", Ed25519PrivateKey.generate(),
        {"publisher": Ed25519PrivateKey.generate().public_key()},
    )
    with pytest.raises(RecoveryCheckpointError, match="timezone-aware"):
        create_recovery_checkpoint(
            authority, Ed25519PrivateKey.generate(), key_id="recovery",
            authority_id="prod", created_at=datetime(2026, 11, 10),
        )
