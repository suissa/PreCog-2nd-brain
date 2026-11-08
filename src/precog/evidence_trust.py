"""Trusted-key registry and revocation policy for evidence attestations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from precog.evidence_attestation import verify_bundle


def _load_registry(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("trust registry must be a regular, non-symlink file")
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("trust registry is unreadable or invalid JSON") from exc
    if not isinstance(registry, dict) or registry.get("version") != 1:
        raise ValueError("unsupported trust registry version")
    keys = registry.get("keys")
    if not isinstance(keys, dict):
        raise ValueError("trust registry must contain a keys object")
    return registry


def verify_with_trust_store(
    bundle: Path,
    *,
    trust_store_path: Path,
    expected_key_id: str | None = None,
    registry_data: dict[str, Any] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Resolve signer policy from a supplied authenticated snapshot or a local registry file."""
    try:
        registry = registry_data if registry_data is not None else _load_registry(trust_store_path)
        if not isinstance(registry, dict) or registry.get("version") != 1 or not isinstance(registry.get("keys"), dict):
            raise ValueError("invalid trust registry structure")
        attestation_path = bundle / "ATTESTATION.json"
        if attestation_path.is_symlink() or not attestation_path.is_file():
            raise ValueError("bundle attestation must be a regular, non-symlink file")
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
        key_id = attestation.get("key_id") if isinstance(attestation, dict) else None
        if not isinstance(key_id, str) or not key_id:
            raise ValueError("attestation has no valid key_id")
        if expected_key_id is not None and key_id != expected_key_id:
            raise ValueError("attestation key_id does not match expected key identity")
        entry = registry["keys"].get(key_id)
        if not isinstance(entry, dict):
            raise ValueError(f"unknown signing key: {key_id}")
        status = entry.get("status")
        if status == "revoked":
            raise ValueError(f"signing key is revoked: {key_id}")
        if status not in {"active", "retired"}:
            raise ValueError(f"invalid trust status for key: {key_id}")
        relative = entry.get("public_key")
        if not isinstance(relative, str) or not relative:
            raise ValueError(f"missing public_key path for key: {key_id}")
        key_path = Path(relative)
        if key_path.is_absolute() or ".." in key_path.parts:
            raise ValueError("public key path must stay inside the trust-store directory")
        root = trust_store_path.parent.resolve()
        resolved = (root / key_path).resolve()
        if resolved.parent != root and root not in resolved.parents:
            raise ValueError("public key path escapes trust-store directory")
        if (root / key_path).is_symlink() or not resolved.is_file():
            raise ValueError("trusted public key must be a regular, non-symlink file")
        valid, errors = verify_bundle(
            bundle, public_key_path=resolved, expected_key_id=key_id
        )
        return valid, errors
    except (OSError, ValueError, TypeError) as exc:
        return False, (str(exc),)
