from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.audit_checkpoint import create_checkpoint
from precog.audit_checkpoint_monitoring import validate_checkpoint_freshness
from precog.audit_integrity import PromotionAuditIntegrityReport


def make_checkpoint(created_at: datetime):
    report = PromotionAuditIntegrityReport(
        valid=True, checked_events=5, legacy_unhashed_events=0, errors=(),
        verified_head_hash="a" * 64,
    )
    return create_checkpoint(
        report, sequence=5, private_key=Ed25519PrivateKey.generate(),
        public_key_id="key-1", created_at=created_at,
    )


def test_fresh_checkpoint_with_normal_append_lag_is_accepted():
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    item = make_checkpoint(now - timedelta(hours=1))
    validate_checkpoint_freshness(
        item, current_sequence=105, max_age_hours=36, max_lag_events=100, now=now
    )


def test_stale_checkpoint_is_rejected():
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    item = make_checkpoint(now - timedelta(hours=37))
    with pytest.raises(ValueError, match="stale"):
        validate_checkpoint_freshness(item, current_sequence=5, now=now)


def test_excessive_sequence_lag_is_rejected_without_calling_it_tampering():
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    item = make_checkpoint(now - timedelta(hours=1))
    with pytest.raises(ValueError, match="lag=101 events"):
        validate_checkpoint_freshness(
            item, current_sequence=106, max_lag_events=100, now=now
        )


def test_history_rollback_is_rejected():
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    item = make_checkpoint(now - timedelta(hours=1))
    with pytest.raises(ValueError, match="shorter"):
        validate_checkpoint_freshness(item, current_sequence=4, now=now)


def test_naive_timestamp_is_rejected():
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    item = replace(make_checkpoint(now - timedelta(hours=1)), created_at="2026-10-13T11:00:00")
    with pytest.raises(ValueError, match="timezone"):
        validate_checkpoint_freshness(item, current_sequence=5, now=now)
