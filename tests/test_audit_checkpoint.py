from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.audit_integrity import PromotionAuditIntegrityReport
from precog.audit_checkpoint import (
    PromotionAuditCheckpoint, create_checkpoint, reconcile_checkpoint,
    verify_checkpoint_signature,
)


NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)


def report(head: str = "a" * 64, valid: bool = True) -> PromotionAuditIntegrityReport:
    return PromotionAuditIntegrityReport(
        valid=valid, checked_events=12, legacy_unhashed_events=2,
        errors=() if valid else ("bad event hash",), verified_head_hash=head,
    )


def test_signed_checkpoint_roundtrip_and_signature_verification():
    private = Ed25519PrivateKey.generate()
    checkpoint = create_checkpoint(
        report(), sequence=14, private_key=private,
        public_key_id="audit-key-2026-01", created_at=NOW,
    )
    loaded = PromotionAuditCheckpoint.from_json(checkpoint.to_json())
    assert loaded == checkpoint
    assert verify_checkpoint_signature(loaded, public_key=private.public_key())


def test_checkpoint_reconciliation_accepts_valid_advanced_history():
    private = Ed25519PrivateKey.generate()
    checkpoint = create_checkpoint(
        report(), sequence=14, private_key=private,
        public_key_id="audit-key", created_at=NOW,
    )
    result = reconcile_checkpoint(
        checkpoint, public_key=private.public_key(), current_report=report("b" * 64),
        current_sequence=18, observed_hash_at_checkpoint="a" * 64,
    )
    assert result.valid
    assert result.current_sequence > result.checkpoint_sequence


def test_checkpoint_detects_rewritten_history_even_if_local_chain_is_valid():
    private = Ed25519PrivateKey.generate()
    checkpoint = create_checkpoint(
        report(), sequence=14, private_key=private,
        public_key_id="audit-key", created_at=NOW,
    )
    result = reconcile_checkpoint(
        checkpoint, public_key=private.public_key(), current_report=report("b" * 64),
        current_sequence=18, observed_hash_at_checkpoint="c" * 64,
    )
    assert not result.valid
    assert any("externally signed checkpoint" in error for error in result.errors)


def test_checkpoint_rejects_invalid_current_chain_and_tampered_signature():
    private = Ed25519PrivateKey.generate()
    checkpoint = create_checkpoint(
        report(), sequence=14, private_key=private,
        public_key_id="audit-key", created_at=NOW,
    )
    tampered = PromotionAuditCheckpoint(
        **{**checkpoint.signed_payload(), "head_hash": "d" * 64},
        signature=checkpoint.signature,
    )
    assert not verify_checkpoint_signature(tampered, public_key=private.public_key())
    result = reconcile_checkpoint(
        checkpoint, public_key=private.public_key(), current_report=report(valid=False),
        current_sequence=14, observed_hash_at_checkpoint="a" * 64,
    )
    assert not result.valid
    assert not result.chain_valid
