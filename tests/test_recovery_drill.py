import base64
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.anchor_recovery import create_recovery_checkpoint
from precog.anchor_service import MonotonicAnchor, canonical_json
from precog.recovery_drill import (
    run_recovery_drill,
    verify_recovery_drill_evidence,
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
    evidence = Ed25519PrivateKey.generate()
    authority = MonotonicAnchor(path, response, {"publisher": publisher.public_key()})
    authority.publish(signed_publish(publisher, 1, "a" * 64, "first"))
    checkpoint = create_recovery_checkpoint(
        authority, recovery, key_id="recovery", authority_id="anchor-prod"
    )
    return authority, publisher, response, recovery, evidence, checkpoint


def run(database, checkpoint, response, recovery, publisher, evidence, run_id="drill-1"):
    return run_recovery_drill(
        database,
        checkpoint,
        {"recovery": recovery.public_key()},
        expected_authority_id="anchor-prod",
        response_signing_key=response,
        publishers={"publisher": publisher.public_key()},
        evidence_signing_key=evidence,
        evidence_key_id="drill-audit",
        run_id=run_id,
    )


def test_recovery_drill_backups_restores_and_signs_passed_evidence(tmp_path):
    database = tmp_path / "anchor.db"
    _, publisher, response, recovery, evidence_key, checkpoint = setup_anchor(database)

    evidence = run(database, checkpoint, response, recovery, publisher, evidence_key)

    assert evidence["payload"]["status"] == "passed"
    assert evidence["payload"]["reason"] == "verified"
    assert len(evidence["payload"]["backup_sha256"]) == 64
    assert evidence["payload"]["restored_state"]["sequence"] == 1
    verified = verify_recovery_drill_evidence(
        evidence, {"drill-audit": evidence_key.public_key()},
        expected_authority_id="anchor-prod",
    )
    assert verified == {"valid": True, "passed": True, "run_id": "drill-1"}


def test_recovery_drill_rejects_stale_checkpoint_after_new_publish(tmp_path):
    database = tmp_path / "anchor.db"
    authority, publisher, response, recovery, evidence_key, checkpoint = setup_anchor(database)
    authority.publish(signed_publish(publisher, 2, "b" * 64, "second"))

    evidence = run(database, checkpoint, response, recovery, publisher, evidence_key)

    assert evidence["payload"]["status"] == "failed"
    assert evidence["payload"]["reason"] == "checkpoint_mismatch_or_untrusted"
    assert evidence["payload"]["restored_state"] is None


def test_recovery_drill_fails_closed_when_checkpoint_is_missing(tmp_path):
    database = tmp_path / "anchor.db"
    _, publisher, response, recovery, evidence_key, _ = setup_anchor(database)

    evidence = run(database, None, response, recovery, publisher, evidence_key)

    assert evidence["payload"]["status"] == "failed"
    assert evidence["payload"]["reason"] == "checkpoint_unavailable"
    assert evidence["payload"]["backup_sha256"] is None


def test_recovery_drill_reports_corrupt_database_without_exposing_details(tmp_path):
    database = tmp_path / "anchor.db"
    _, publisher, response, recovery, evidence_key, checkpoint = setup_anchor(database)
    database.write_bytes(b"not a sqlite database")

    evidence = run(database, checkpoint, response, recovery, publisher, evidence_key)

    assert evidence["payload"]["status"] == "failed"
    assert evidence["payload"]["reason"] == "backup_or_restore_failed"
    assert str(tmp_path) not in str(evidence)


def test_recovery_drill_evidence_rejects_tampering_and_unknown_signer(tmp_path):
    database = tmp_path / "anchor.db"
    _, publisher, response, recovery, evidence_key, checkpoint = setup_anchor(database)
    evidence = run(database, checkpoint, response, recovery, publisher, evidence_key)
    evidence["payload"]["status"] = "passed"

    import pytest
    from precog.recovery_drill import RecoveryDrillError

    with pytest.raises(RecoveryDrillError, match="signature"):
        verify_recovery_drill_evidence(
            evidence, {"drill-audit": evidence_key.public_key()},
            expected_authority_id="anchor-prod",
        )
    evidence["payload"]["status"] = "failed"
    with pytest.raises(RecoveryDrillError, match="untrusted"):
        verify_recovery_drill_evidence(
            evidence, {}, expected_authority_id="anchor-prod"
        )
