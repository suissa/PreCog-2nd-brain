"""Ed25519 attestations for immutable PreCog operational evidence bundles."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ATTESTATION_FILE = "ATTESTATION.json"
VERSION = 1


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _load_private(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private key must be Ed25519")
    return key


def _load_public(path: Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("public key must be Ed25519")
    return key


def _bundle_files(root: Path) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("bundle must be a real directory")
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlinks are not allowed in evidence bundle: {path.relative_to(root)}")
        if not path.is_file() or path.name == ATTESTATION_FILE:
            continue
        relative = path.relative_to(root).as_posix()
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not files:
        raise ValueError("bundle contains no evidence files")
    return files


def sign_bundle(bundle: Path, *, private_key_path: Path, key_id: str) -> Path:
    """Create a detached, no-overwrite attestation binding all bundle files and metadata."""
    if not key_id.strip():
        raise ValueError("key_id must not be empty")
    destination = bundle / ATTESTATION_FILE
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to overwrite {destination}")
    payload = {
        "version": VERSION,
        "key_id": key_id,
        "algorithm": "Ed25519",
        "files": _bundle_files(bundle),
    }
    signature = base64.b64encode(_load_private(private_key_path).sign(_canonical(payload))).decode("ascii")
    document = {**payload, "signature": signature}
    # O_EXCL prevents overwriting an existing attestation.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(document, stream, sort_keys=True, indent=2, ensure_ascii=False)
        stream.write("\\n")
    return destination


def verify_bundle(bundle: Path, *, public_key_path: Path, expected_key_id: str | None = None) -> tuple[bool, tuple[str, ...]]:
    """Verify signature, key identity, and exact file inventory/content."""
    errors: list[str] = []
    attestation = bundle / ATTESTATION_FILE
    try:
        raw = json.loads(attestation.read_text(encoding="utf-8"))
        signature = base64.b64decode(raw.pop("signature"), validate=True)
        payload = raw
        if payload.get("version") != VERSION or payload.get("algorithm") != "Ed25519":
            errors.append("unsupported attestation version or algorithm")
        key_id = payload.get("key_id")
        if expected_key_id is not None and key_id != expected_key_id:
            errors.append("attestation key_id does not match trusted key identity")
        _load_public(public_key_path).verify(signature, _canonical(payload))
    except (OSError, ValueError, KeyError, TypeError, InvalidSignature, json.JSONDecodeError) as exc:
        errors.append(f"signature/attestation verification failed: {type(exc).__name__}")
        return False, tuple(errors)

    try:
        actual = _bundle_files(bundle)
        expected = payload.get("files")
        if not isinstance(expected, dict):
            errors.append("attestation files inventory is malformed")
        elif actual != expected:
            errors.append("bundle file inventory or content hash differs from attestation")
    except (OSError, ValueError) as exc:
        errors.append(f"bundle inspection failed: {exc}")
    return not errors, tuple(errors)
