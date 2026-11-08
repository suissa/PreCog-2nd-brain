import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.evidence_attestation import sign_bundle
from precog.evidence_trust import verify_with_trust_store


def _fixture(tmp_path: Path, status: str = "active") -> tuple[Path, Path]:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "evidence.txt").write_text("checkpoint evidence\n")
    private = Ed25519PrivateKey.generate()
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "ops-a.pem"
    private_path.write_bytes(private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public_path.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    sign_bundle(bundle, private_key_path=private_path, key_id="ops-a")
    registry = tmp_path / "trust.json"
    registry.write_text(json.dumps({
        "version": 1,
        "keys": {"ops-a": {"public_key": "ops-a.pem", "status": status}},
    }))
    return bundle, registry


def test_trust_store_accepts_active_and_retired_keys(tmp_path: Path) -> None:
    for status in ("active", "retired"):
        case = tmp_path / status
        case.mkdir()
        bundle, registry = _fixture(case, status)
        valid, errors = verify_with_trust_store(bundle, trust_store_path=registry)
        assert valid and not errors


def test_trust_store_rejects_revoked_and_unknown_keys(tmp_path: Path) -> None:
    bundle, registry = _fixture(tmp_path, "revoked")
    valid, errors = verify_with_trust_store(bundle, trust_store_path=registry)
    assert not valid and "revoked" in " ".join(errors)

    registry.write_text(json.dumps({"version": 1, "keys": {}}))
    valid, errors = verify_with_trust_store(bundle, trust_store_path=registry)
    assert not valid and "unknown" in " ".join(errors)


def test_trust_store_rejects_path_traversal_and_symlinked_key(tmp_path: Path) -> None:
    bundle, registry = _fixture(tmp_path)
    registry.write_text(json.dumps({
        "version": 1,
        "keys": {"ops-a": {"public_key": "../private.pem", "status": "active"}},
    }))
    valid, errors = verify_with_trust_store(bundle, trust_store_path=registry)
    assert not valid and "inside" in " ".join(errors)

    key = tmp_path / "ops-a.pem"
    target = tmp_path / "copy.pem"
    target.write_bytes(key.read_bytes())
    key.unlink()
    key.symlink_to(target)
    registry.write_text(json.dumps({
        "version": 1,
        "keys": {"ops-a": {"public_key": "ops-a.pem", "status": "active"}},
    }))
    valid, errors = verify_with_trust_store(bundle, trust_store_path=registry)
    assert not valid and "non-symlink" in " ".join(errors)


def test_trust_store_enforces_expected_identity_and_registry_version(tmp_path: Path) -> None:
    bundle, registry = _fixture(tmp_path)
    valid, errors = verify_with_trust_store(
        bundle, trust_store_path=registry, expected_key_id="other"
    )
    assert not valid and "expected key identity" in " ".join(errors)
    registry.write_text(json.dumps({"version": 2, "keys": {}}))
    valid, errors = verify_with_trust_store(bundle, trust_store_path=registry)
    assert not valid and "version" in " ".join(errors)
