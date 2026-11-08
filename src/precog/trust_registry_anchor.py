"""Verify a signed registry against an independently operated monotonic anchor."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _load_anchor_key(path: Path) -> Ed25519PublicKey:
    if path.is_symlink() or not path.is_file():
        raise ValueError("anchor public key must be a regular, non-symlink file")
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("anchor public key must be Ed25519")
    return key


def verify_registry_anchor(
    registry: dict[str, Any],
    *,
    anchor_url: str,
    anchor_public_key_path: Path,
    timeout: float = 5.0,
) -> tuple[bool, tuple[str, ...]]:
    """Require the local signed registry to equal the independently anchored head."""
    try:
        parsed = urlsplit(anchor_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("anchor URL must be an HTTPS URL without embedded credentials")
        sequence = registry.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("anchored trust registry must contain a positive integer sequence")
        digest = hashlib.sha256(_canonical(registry)).hexdigest()
        nonce = secrets.token_urlsafe(24)
        endpoint = anchor_url.rstrip("/") + "/v1/trust-registry/head"
        request = Request(
            endpoint + "?nonce=" + nonce,
            headers={"Accept": "application/json", "Cache-Control": "no-store"},
            method="GET",
        )
        with urlopen(request, timeout=timeout) as response:
            if response.geturl().split(":", 1)[0].lower() != "https":
                raise ValueError("anchor endpoint redirected away from HTTPS")
            envelope = json.loads(response.read())
        if not isinstance(envelope, dict):
            raise ValueError("anchor response must be a JSON object")
        payload = envelope.get("payload")
        signature_text = envelope.get("signature")
        if not isinstance(payload, dict) or not isinstance(signature_text, str):
            raise ValueError("anchor response must contain payload and signature")
        required = {"version", "sequence", "registry_sha256", "nonce"}
        if set(payload) != required or payload.get("version") != 1:
            raise ValueError("unsupported or malformed anchor payload")
        if payload.get("nonce") != nonce:
            raise ValueError("anchor response nonce mismatch")
        anchor_sequence = payload.get("sequence")
        if isinstance(anchor_sequence, bool) or not isinstance(anchor_sequence, int) or anchor_sequence < 1:
            raise ValueError("anchor sequence must be a positive integer")
        anchor_digest = payload.get("registry_sha256")
        if not isinstance(anchor_digest, str) or len(anchor_digest) != 64:
            raise ValueError("anchor registry digest is malformed")
        signature = base64.b64decode(signature_text, validate=True)
        _load_anchor_key(anchor_public_key_path).verify(signature, _canonical(payload))
        if anchor_sequence != sequence or anchor_digest != digest:
            raise ValueError(
                "trust registry rollback or divergence detected: "
                f"local sequence={sequence} digest={digest}; "
                f"anchor sequence={anchor_sequence} digest={anchor_digest}"
            )
        return True, ()
    except (
        OSError, ValueError, TypeError, json.JSONDecodeError, InvalidSignature, URLError
    ) as exc:
        return False, (f"trust registry monotonic-anchor verification failed: {type(exc).__name__}: {exc}",)
