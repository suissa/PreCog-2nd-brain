"""Detached Ed25519 signatures for local trusted-key registries."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SIGNATURE_SUFFIX = ".sig"


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("registry signing key must be Ed25519")
    return key


def _public_key(path: Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("registry root key must be Ed25519")
    return key


def sign_trust_registry(registry_path: Path, *, private_key_path: Path) -> Path:
    """Sign canonical registry content into a detached, no-overwrite sidecar."""
    if registry_path.is_symlink() or not registry_path.is_file():
        raise ValueError("trust registry must be a regular, non-symlink file")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(registry, dict) or registry.get("version") != 1 or not isinstance(registry.get("keys"), dict):
        raise ValueError("invalid trust registry structure")
    signature_path = registry_path.with_name(registry_path.name + SIGNATURE_SUFFIX)
    if signature_path.exists() or signature_path.is_symlink():
        raise FileExistsError(f"refusing to overwrite {signature_path}")
    signature = base64.b64encode(_private_key(private_key_path).sign(_canonical(registry))) + b"\n"
    fd = os.open(signature_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(signature)
    return signature_path


def verify_signed_trust_registry(
    registry_path: Path, *, root_public_key_path: Path
) -> tuple[bool, tuple[str, ...]]:
    """Verify registry authenticity against an independently provisioned root public key."""
    signature_path = registry_path.with_name(registry_path.name + SIGNATURE_SUFFIX)
    try:
        if registry_path.is_symlink() or not registry_path.is_file():
            raise ValueError("trust registry must be a regular, non-symlink file")
        if signature_path.is_symlink() or not signature_path.is_file():
            raise ValueError("trust registry signature must be a regular, non-symlink file")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(registry, dict) or registry.get("version") != 1 or not isinstance(registry.get("keys"), dict):
            raise ValueError("invalid trust registry structure")
        signature = base64.b64decode(signature_path.read_bytes().strip(), validate=True)
        _public_key(root_public_key_path).verify(signature, _canonical(registry))
        return True, ()
    except (OSError, ValueError, TypeError, json.JSONDecodeError, InvalidSignature) as exc:
        return False, (f"trust registry signature verification failed: {type(exc).__name__}: {exc}",)
