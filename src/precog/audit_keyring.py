from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .audit_checkpoint import PromotionAuditCheckpoint, verify_checkpoint_signature


class AuditKeyStatus(str, Enum):
    ACTIVE = "active"
    VERIFY_ONLY = "verify_only"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class AuditPublicKey:
    key_id: str
    public_key_pem: bytes
    status: AuditKeyStatus


class AuditPublicKeyring:
    """Resolve checkpoint key IDs while retaining historical verification keys.

    ACTIVE identifies the current signing key operationally; this class never
    holds private keys. VERIFY_ONLY keys remain valid for historical signatures.
    REVOKED keys fail closed, including for previously valid checkpoints.
    """

    def __init__(self, keys: tuple[AuditPublicKey, ...]) -> None:
        indexed: dict[str, AuditPublicKey] = {}
        active_count = 0
        for item in keys:
            if not item.key_id.strip():
                raise ValueError("audit key ID must be non-empty")
            if item.key_id in indexed:
                raise ValueError(f"duplicate audit key ID: {item.key_id}")
            if item.status is AuditKeyStatus.ACTIVE:
                active_count += 1
            indexed[item.key_id] = item
        if active_count > 1:
            raise ValueError("keyring must have at most one active signing key")
        self._keys = indexed

    def verify(self, checkpoint: PromotionAuditCheckpoint) -> bool:
        record = self._keys.get(checkpoint.public_key_id)
        if record is None or record.status is AuditKeyStatus.REVOKED:
            return False
        try:
            key = serialization.load_pem_public_key(record.public_key_pem)
        except (ValueError, TypeError):
            return False
        if not isinstance(key, Ed25519PublicKey):
            return False
        return verify_checkpoint_signature(checkpoint, public_key=key)

    @property
    def active_key_id(self) -> str | None:
        for record in self._keys.values():
            if record.status is AuditKeyStatus.ACTIVE:
                return record.key_id
        return None
