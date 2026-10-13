from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .audit_checkpoint import (
    PromotionAuditCheckpoint,
    PromotionAuditReconciliation,
    verify_checkpoint_signature,
)
from .audit_integrity import GENESIS_HASH, PromotionAuditIntegrityReport


class AuditCheckpointLog(Protocol):
    def verify_integrity(self) -> PromotionAuditIntegrityReport: ...
    def latest_checkpoint_position(self) -> tuple[int, str]: ...
    def export_checkpoint(
        self, *, private_key: bytes, public_key_id: str
    ) -> PromotionAuditCheckpoint: ...
    def reconcile_checkpoint(
        self, checkpoint: PromotionAuditCheckpoint, *, public_key: Ed25519PublicKey | bytes
    ) -> PromotionAuditReconciliation: ...


class CheckpointStore(Protocol):
    def write(self, checkpoint: PromotionAuditCheckpoint) -> Path: ...
    def latest(self) -> PromotionAuditCheckpoint | None: ...


class AuditAlertSink(Protocol):
    def alert(self, message: str) -> None: ...


class StderrAuditAlertSink:
    """Minimal alert sink; production deployments can inject email, webhook or paging."""

    def alert(self, message: str) -> None:
        import sys
        print(f"PRECOG AUDIT ALERT: {message}", file=sys.stderr, flush=True)


class FileCheckpointStore:
    """Filesystem checkpoint store with atomic publication and no-overwrite semantics.

    The directory must be outside the database trust boundary. A local directory on
    the same host is operationally convenient, but is not independent against a
    host/root compromise.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def write(self, checkpoint: PromotionAuditCheckpoint) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        name = f"checkpoint-{checkpoint.sequence:020d}-{checkpoint.head_hash}.json"
        destination = self.directory / name
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.directory,
                prefix=".checkpoint-", suffix=".tmp", delete=False,
            ) as stream:
                temporary_name = stream.name
                stream.write(checkpoint.to_json())
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            # A hard link publishes the complete file atomically and fails if the
            # destination already exists; it never silently overwrites a checkpoint.
            os.link(temporary_name, destination)
            directory_fd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return destination
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass

    def latest(self) -> PromotionAuditCheckpoint | None:
        if not self.directory.exists():
            return None
        checkpoints: list[PromotionAuditCheckpoint] = []
        for path in self.directory.glob("checkpoint-*.json"):
            checkpoints.append(PromotionAuditCheckpoint.from_json(path.read_text(encoding="utf-8")))
        if not checkpoints:
            return None
        return max(checkpoints, key=lambda item: (item.sequence, item.created_at))


class PublicKeyRegistry:
    """Resolve retained public keys by stable key ID; unknown IDs fail closed."""

    _SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def load(self, key_id: str) -> bytes:
        if not self._SAFE_ID.fullmatch(key_id):
            raise ValueError("checkpoint contains an unsafe public key ID")
        path = self.directory / f"{key_id}.pem"
        try:
            return path.read_bytes()
        except FileNotFoundError as error:
            raise ValueError(f"no trusted public key registered for key ID: {key_id}") from error


class CheckpointJob:
    """One-shot checkpoint/reconciliation job intended for cron, systemd or a scheduler."""

    def __init__(
        self,
        *,
        audit_log: AuditCheckpointLog,
        checkpoint_store: CheckpointStore,
        public_keys: PublicKeyRegistry,
        alert_sink: AuditAlertSink,
    ) -> None:
        self.audit_log = audit_log
        self.checkpoint_store = checkpoint_store
        self.public_keys = public_keys
        self.alert_sink = alert_sink

    def create(self, *, private_key: bytes, public_key_id: str) -> Path:
        try:
            before = self.audit_log.verify_integrity()
            if not before.valid:
                raise RuntimeError("audit chain failed verification: " + "; ".join(before.errors))
            sequence, head_hash = self.audit_log.latest_checkpoint_position()
            if head_hash != before.verified_head_hash:
                raise RuntimeError("verified audit head and latest stored event disagree")
            checkpoint = self.audit_log.export_checkpoint(
                private_key=private_key, public_key_id=public_key_id
            )
            if checkpoint.sequence != sequence or checkpoint.head_hash != head_hash:
                raise RuntimeError("audit history changed during checkpoint creation; retry")
            if not verify_checkpoint_signature(
                checkpoint, public_key=self.public_keys.load(public_key_id)
            ):
                raise RuntimeError("new checkpoint failed self-verification")
            # Recheck after signing to narrow the window for concurrent modifications.
            after = self.audit_log.verify_integrity()
            current_sequence, current_hash = self.audit_log.latest_checkpoint_position()
            if (
                not after.valid
                or current_sequence != sequence
                or current_hash != head_hash
                or after.verified_head_hash != head_hash
            ):
                raise RuntimeError("audit history changed before checkpoint publication")
            return self.checkpoint_store.write(checkpoint)
        except Exception as error:
            self.alert_sink.alert(f"checkpoint creation failed: {error}")
            raise

    def reconcile_latest(self) -> PromotionAuditReconciliation:
        try:
            checkpoint = self.checkpoint_store.latest()
            if checkpoint is None:
                raise RuntimeError("no external audit checkpoint is available")
            public_key = self.public_keys.load(checkpoint.public_key_id)
            result = self.audit_log.reconcile_checkpoint(checkpoint, public_key=public_key)
            if not result.valid:
                raise RuntimeError("checkpoint reconciliation failed: " + "; ".join(result.errors))
            return result
        except Exception as error:
            self.alert_sink.alert(f"checkpoint reconciliation failed: {error}")
            raise
