import base64
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.trust_registry_anchor import verify_registry_anchor


def _canonical(value: dict[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _key_files(tmp_path: Path) -> tuple[Ed25519PrivateKey, Path]:
    private = Ed25519PrivateKey.generate()
    public_path = tmp_path / "anchor-public.pem"
    public_path.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return private, public_path


class _Response:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = json.dumps(body).encode()

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body

    def geturl(self) -> str:
        return "https://anchor.example/v1/trust-registry/head"


def _anchor_response(private: Ed25519PrivateKey, registry: dict[str, object], nonce: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": 1,
        "sequence": registry["sequence"],
        "registry_sha256": hashlib.sha256(_canonical(registry)).hexdigest(),
        "nonce": nonce,
    }
    return {
        "payload": payload,
        "signature": base64.b64encode(private.sign(_canonical(payload))).decode(),
    }


def test_anchor_accepts_exact_signed_head(tmp_path: Path) -> None:
    private, public = _key_files(tmp_path)
    registry: dict[str, object] = {"version": 1, "sequence": 8, "keys": {}}

    def fake_urlopen(request: object, timeout: float) -> _Response:
        nonce = request.full_url.split("nonce=", 1)[1]
        return _Response(_anchor_response(private, registry, nonce))

    with patch("precog.trust_registry_anchor.urlopen", side_effect=fake_urlopen):
        valid, errors = verify_registry_anchor(
            registry, anchor_url="https://anchor.example", anchor_public_key_path=public
        )
    assert valid and not errors


def test_anchor_rejects_rollback_and_divergent_content(tmp_path: Path) -> None:
    private, public = _key_files(tmp_path)
    registry: dict[str, object] = {"version": 1, "sequence": 8, "keys": {}}

    def fake_urlopen(request: object, timeout: float) -> _Response:
        nonce = request.full_url.split("nonce=", 1)[1]
        stale = dict(registry, sequence=7)
        return _Response(_anchor_response(private, stale, nonce))

    with patch("precog.trust_registry_anchor.urlopen", side_effect=fake_urlopen):
        valid, errors = verify_registry_anchor(
            registry, anchor_url="https://anchor.example", anchor_public_key_path=public
        )
    assert not valid and "rollback or divergence" in " ".join(errors)


def test_anchor_rejects_replayed_nonce_and_bad_signature(tmp_path: Path) -> None:
    private, public = _key_files(tmp_path)
    registry: dict[str, object] = {"version": 1, "sequence": 1, "keys": {}}

    def replayed(request: object, timeout: float) -> _Response:
        return _Response(_anchor_response(private, registry, "previous-request-nonce"))

    with patch("precog.trust_registry_anchor.urlopen", side_effect=replayed):
        valid, errors = verify_registry_anchor(
            registry, anchor_url="https://anchor.example", anchor_public_key_path=public
        )
    assert not valid and "nonce mismatch" in " ".join(errors)

    def forged(request: object, timeout: float) -> _Response:
        nonce = request.full_url.split("nonce=", 1)[1]
        envelope = _anchor_response(private, registry, nonce)
        envelope["signature"] = base64.b64encode(b"not-a-signature").decode()
        return _Response(envelope)

    with patch("precog.trust_registry_anchor.urlopen", side_effect=forged):
        valid, errors = verify_registry_anchor(
            registry, anchor_url="https://anchor.example", anchor_public_key_path=public
        )
    assert not valid and errors
