import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.evidence_trust import verify_with_trust_store
from precog.evidence_trust_signature import (
    load_verified_trust_registry,
    sign_trust_registry,
    verify_signed_trust_registry,
)


def _keys(tmp_path: Path) -> tuple[Path, Path]:
    private = Ed25519PrivateKey.generate()
    private_path = tmp_path / "root-private.pem"
    public_path = tmp_path / "root-public.pem"
    private_path.write_bytes(private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public_path.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return private_path, public_path


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "trust.json"
    path.write_text(json.dumps({
        "version": 1,
        "keys": {"ops-a": {"public_key": "ops-a.pem", "status": "active"}},
    }))
    return path


def test_signed_registry_verifies_with_out_of_band_root_key(tmp_path: Path) -> None:
    private, public = _keys(tmp_path)
    registry = _registry(tmp_path)
    signature = sign_trust_registry(registry, private_key_path=private)
    assert signature == tmp_path / "trust.json.sig"
    valid, errors = verify_signed_trust_registry(registry, root_public_key_path=public)
    assert valid and not errors


def test_signed_registry_detects_tampering(tmp_path: Path) -> None:
    private, public = _keys(tmp_path)
    registry = _registry(tmp_path)
    sign_trust_registry(registry, private_key_path=private)
    registry.write_text(json.dumps({
        "version": 1,
        "keys": {"attacker": {"public_key": "attacker.pem", "status": "active"}},
    }))
    valid, errors = verify_signed_trust_registry(registry, root_public_key_path=public)
    assert not valid and "verification failed" in " ".join(errors)


def test_signed_registry_rejects_wrong_root_and_missing_signature(tmp_path: Path) -> None:
    private, public = _keys(tmp_path)
    wrong_dir = tmp_path / "wrong"
    wrong_dir.mkdir()
    _, wrong_public = _keys(wrong_dir)
    registry = _registry(tmp_path)
    sign_trust_registry(registry, private_key_path=private)
    valid, errors = verify_signed_trust_registry(registry, root_public_key_path=wrong_public)
    assert not valid and errors
    (tmp_path / "trust.json.sig").unlink()
    valid, errors = verify_signed_trust_registry(registry, root_public_key_path=public)
    assert not valid and "signature" in " ".join(errors)


def test_signed_registry_refuses_overwrite_and_symlinks(tmp_path: Path) -> None:
    private, public = _keys(tmp_path)
    registry = _registry(tmp_path)
    sign_trust_registry(registry, private_key_path=private)
    try:
        sign_trust_registry(registry, private_key_path=private)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected no-overwrite behavior")
    registry_link = tmp_path / "linked.json"
    registry_link.symlink_to(registry)
    valid, errors = verify_signed_trust_registry(registry_link, root_public_key_path=public)
    assert not valid and errors



def test_verification_uses_the_exact_authenticated_registry_snapshot(tmp_path: Path) -> None:
    private, public = _keys(tmp_path)
    registry_path = _registry(tmp_path)
    sign_trust_registry(registry_path, private_key_path=private)

    registry_snapshot, errors = load_verified_trust_registry(
        registry_path, root_public_key_path=public
    )
    assert registry_snapshot is not None and not errors

    # Simulate replacement after signature validation. The verifier must not
    # re-open the path and consume this unauthenticated replacement.
    registry_path.write_text(json.dumps({
        "version": 1,
        "keys": {"attacker": {"public_key": "attacker.pem", "status": "revoked"}},
    }))
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "ATTESTATION.json").write_text(json.dumps({"key_id": "attacker"}))

    valid, verify_errors = verify_with_trust_store(
        bundle,
        trust_store_path=registry_path,
        registry_data=registry_snapshot,
    )
    assert not valid
    assert "unknown signing key: attacker" in " ".join(verify_errors)
