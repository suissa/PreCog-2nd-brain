from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.audit_checkpoint import create_checkpoint
from precog.audit_checkpoint_ops import (
    CheckpointJob, FileCheckpointStore, PublicKeyRegistry,
)
from precog.audit_integrity import PromotionAuditIntegrityReport


class Alerts:
    def __init__(self):
        self.messages = []

    def alert(self, message: str) -> None:
        self.messages.append(message)


class FakeLog:
    def __init__(self):
        self.sequence = 3
        self.head = "a" * 64
        self.valid = True

    def verify_integrity(self):
        return PromotionAuditIntegrityReport(
            valid=self.valid, checked_events=self.sequence, legacy_unhashed_events=0,
            errors=() if self.valid else ("broken",), verified_head_hash=self.head,
        )

    def latest_checkpoint_position(self):
        return self.sequence, self.head

    def export_checkpoint(self, *, private_key: bytes, public_key_id: str):
        return create_checkpoint(
            self.verify_integrity(), sequence=self.sequence,
            private_key=private_key, public_key_id=public_key_id,
        )

    def reconcile_checkpoint(self, checkpoint, *, public_key):
        from precog.audit_checkpoint import reconcile_checkpoint
        return reconcile_checkpoint(
            checkpoint, public_key=public_key, current_report=self.verify_integrity(),
            current_sequence=self.sequence, observed_hash_at_checkpoint=self.head,
        )


def write_keys(tmp_path: Path, key_id: str, private: Ed25519PrivateKey) -> tuple[Path, Path]:
    private_dir = tmp_path / "private"
    public_dir = tmp_path / "public"
    private_dir.mkdir()
    public_dir.mkdir()
    private_path = private_dir / "signing.pem"
    private_path.write_bytes(private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    (public_dir / f"{key_id}.pem").write_bytes(private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return private_path, public_dir


def test_file_store_atomically_publishes_and_never_overwrites(tmp_path):
    private = Ed25519PrivateKey.generate()
    checkpoint = create_checkpoint(
        FakeLog().verify_integrity(), sequence=3, private_key=private,
        public_key_id="key-1",
    )
    store = FileCheckpointStore(tmp_path / "checkpoints")
    path = store.write(checkpoint)
    assert store.latest() == checkpoint
    with pytest.raises(FileExistsError):
        store.write(checkpoint)
    assert path.read_text(encoding="utf-8").strip() == checkpoint.to_json()
    assert not list(path.parent.glob("*.tmp"))


def test_job_creates_checkpoint_after_verifying_key_and_stable_head(tmp_path):
    private = Ed25519PrivateKey.generate()
    private_path, public_dir = write_keys(tmp_path, "key-1", private)
    log = FakeLog()
    store = FileCheckpointStore(tmp_path / "checkpoints")
    alerts = Alerts()
    job = CheckpointJob(
        audit_log=log, checkpoint_store=store,
        public_keys=PublicKeyRegistry(public_dir), alert_sink=alerts,
    )
    result_path = job.create(private_key=private_path.read_bytes(), public_key_id="key-1")
    assert result_path.exists()
    assert store.latest().sequence == 3
    assert alerts.messages == []


def test_job_fails_closed_and_alerts_on_invalid_chain(tmp_path):
    private = Ed25519PrivateKey.generate()
    _, public_dir = write_keys(tmp_path, "key-1", private)
    log = FakeLog()
    log.valid = False
    alerts = Alerts()
    job = CheckpointJob(
        audit_log=log, checkpoint_store=FileCheckpointStore(tmp_path / "checkpoints"),
        public_keys=PublicKeyRegistry(public_dir), alert_sink=alerts,
    )
    with pytest.raises(RuntimeError, match="failed verification"):
        job.create(private_key=b"unused", public_key_id="key-1")
    assert len(alerts.messages) == 1


def test_registry_rejects_unknown_and_unsafe_key_ids(tmp_path):
    registry = PublicKeyRegistry(tmp_path)
    with pytest.raises(ValueError, match="unsafe"):
        registry.load("../outside")
    with pytest.raises(ValueError, match="no trusted public key"):
        registry.load("retired-key")
