from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.audit_checkpoint import create_checkpoint
from precog.audit_integrity import PromotionAuditIntegrityReport
from precog.audit_keyring import AuditKeyStatus, AuditPublicKey, AuditPublicKeyring


def signed_checkpoint(key: Ed25519PrivateKey, key_id: str):
    report = PromotionAuditIntegrityReport(
        valid=True, checked_events=4, legacy_unhashed_events=0,
        errors=(), verified_head_hash="f" * 64,
    )
    return create_checkpoint(
        report, sequence=4, private_key=key, public_key_id=key_id,
        created_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
    )


def public_pem(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def test_keyring_verifies_old_key_after_rotation() -> None:
    old = Ed25519PrivateKey.generate()
    current = Ed25519PrivateKey.generate()
    ring = AuditPublicKeyring((
        AuditPublicKey("old-2026-01", public_pem(old), AuditKeyStatus.VERIFY_ONLY),
        AuditPublicKey("current-2026-02", public_pem(current), AuditKeyStatus.ACTIVE),
    ))

    assert ring.active_key_id == "current-2026-02"
    assert ring.verify(signed_checkpoint(old, "old-2026-01"))
    assert ring.verify(signed_checkpoint(current, "current-2026-02"))


def test_keyring_fails_closed_for_revoked_or_unknown_key() -> None:
    old = Ed25519PrivateKey.generate()
    ring = AuditPublicKeyring((
        AuditPublicKey("revoked", public_pem(old), AuditKeyStatus.REVOKED),
    ))

    assert not ring.verify(signed_checkpoint(old, "revoked"))
    assert not ring.verify(signed_checkpoint(old, "unknown"))


def test_keyring_rejects_duplicate_ids_and_multiple_active_keys() -> None:
    first = Ed25519PrivateKey.generate()
    second = Ed25519PrivateKey.generate()
    duplicate = AuditPublicKey("same", public_pem(first), AuditKeyStatus.ACTIVE)
    import pytest
    with pytest.raises(ValueError, match="duplicate"):
        AuditPublicKeyring((duplicate, duplicate))
    with pytest.raises(ValueError, match="at most one"):
        AuditPublicKeyring((
            duplicate,
            AuditPublicKey("other", public_pem(second), AuditKeyStatus.ACTIVE),
        ))
