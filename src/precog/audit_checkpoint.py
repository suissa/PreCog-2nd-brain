from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .audit_integrity import PromotionAuditIntegrityReport


CHECKPOINT_VERSION = 1


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _private_key(key: Ed25519PrivateKey | bytes) -> Ed25519PrivateKey:
    if isinstance(key, Ed25519PrivateKey):
        return key
    try:
        loaded = serialization.load_pem_private_key(key, password=None)
    except ValueError:
        loaded = Ed25519PrivateKey.from_private_bytes(key)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise TypeError("private key must be Ed25519")
    return loaded


def _public_key(key: Ed25519PublicKey | bytes) -> Ed25519PublicKey:
    if isinstance(key, Ed25519PublicKey):
        return key
    try:
        loaded = serialization.load_pem_public_key(key)
    except ValueError:
        loaded = Ed25519PublicKey.from_public_bytes(key)
    if not isinstance(loaded, Ed25519PublicKey):
        raise TypeError("public key must be Ed25519")
    return loaded


@dataclass(frozen=True, slots=True)
class PromotionAuditCheckpoint:
    version: int
    sequence: int
    head_hash: str
    checked_events: int
    legacy_unhashed_events: int
    created_at: str
    public_key_id: str
    signature: str

    def signed_payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sequence": self.sequence,
            "head_hash": self.head_hash,
            "checked_events": self.checked_events,
            "legacy_unhashed_events": self.legacy_unhashed_events,
            "created_at": self.created_at,
            "public_key_id": self.public_key_id,
        }

    def to_json(self) -> str:
        return json.dumps(
            {**self.signed_payload(), "signature": self.signature},
            sort_keys=True, indent=2, ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, value: str) -> PromotionAuditCheckpoint:
        raw = json.loads(value)
        return cls(
            version=int(raw["version"]), sequence=int(raw["sequence"]),
            head_hash=str(raw["head_hash"]), checked_events=int(raw["checked_events"]),
            legacy_unhashed_events=int(raw["legacy_unhashed_events"]),
            created_at=str(raw["created_at"]), public_key_id=str(raw["public_key_id"]),
            signature=str(raw["signature"]),
        )


def create_checkpoint(
    report: PromotionAuditIntegrityReport,
    *,
    sequence: int,
    private_key: Ed25519PrivateKey | bytes,
    public_key_id: str,
    created_at: datetime | None = None,
) -> PromotionAuditCheckpoint:
    if not report.valid:
        raise ValueError("cannot checkpoint an invalid audit chain")
    if sequence < 0:
        raise ValueError("sequence must be non-negative")
    if not public_key_id.strip():
        raise ValueError("public_key_id must be non-empty")
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    key = _private_key(private_key)
    payload = {
        "version": CHECKPOINT_VERSION,
        "sequence": sequence,
        "head_hash": report.verified_head_hash,
        "checked_events": report.checked_events,
        "legacy_unhashed_events": report.legacy_unhashed_events,
        "created_at": timestamp.astimezone(timezone.utc).isoformat(),
        "public_key_id": public_key_id,
    }
    signature = base64.b64encode(key.sign(_canonical(payload))).decode("ascii")
    return PromotionAuditCheckpoint(**payload, signature=signature)


def verify_checkpoint_signature(
    checkpoint: PromotionAuditCheckpoint,
    *,
    public_key: Ed25519PublicKey | bytes,
) -> bool:
    if checkpoint.version != CHECKPOINT_VERSION:
        return False
    try:
        signature = base64.b64decode(checkpoint.signature, validate=True)
        _public_key(public_key).verify(signature, _canonical(checkpoint.signed_payload()))
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


@dataclass(frozen=True, slots=True)
class PromotionAuditReconciliation:
    valid: bool
    signature_valid: bool
    chain_valid: bool
    checkpoint_sequence: int
    current_sequence: int
    checkpoint_hash: str
    observed_hash_at_checkpoint: str | None
    current_head_hash: str
    errors: tuple[str, ...]


def reconcile_checkpoint(
    checkpoint: PromotionAuditCheckpoint,
    *,
    public_key: Ed25519PublicKey | bytes,
    current_report: PromotionAuditIntegrityReport,
    current_sequence: int,
    observed_hash_at_checkpoint: str | None,
) -> PromotionAuditReconciliation:
    signature_valid = verify_checkpoint_signature(checkpoint, public_key=public_key)
    errors: list[str] = []
    if not signature_valid:
        errors.append("checkpoint signature is invalid or key/version is unsupported")
    if not current_report.valid:
        errors.append("current audit chain failed integrity verification")
    if current_sequence < checkpoint.sequence:
        errors.append("current audit history is shorter than the signed checkpoint")
    if observed_hash_at_checkpoint != checkpoint.head_hash:
        errors.append("stored history does not match the externally signed checkpoint")
    return PromotionAuditReconciliation(
        valid=signature_valid and current_report.valid and current_sequence >= checkpoint.sequence
        and observed_hash_at_checkpoint == checkpoint.head_hash,
        signature_valid=signature_valid,
        chain_valid=current_report.valid,
        checkpoint_sequence=checkpoint.sequence,
        current_sequence=current_sequence,
        checkpoint_hash=checkpoint.head_hash,
        observed_hash_at_checkpoint=observed_hash_at_checkpoint,
        current_head_hash=current_report.verified_head_hash,
        errors=tuple(errors),
    )
