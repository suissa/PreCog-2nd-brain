from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.evidence_attestation import ATTESTATION_FILE, sign_bundle, verify_bundle


def _keys(tmp_path: Path) -> tuple[Path, Path]:
    private = Ed25519PrivateKey.generate()
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    private_path.chmod(0o600)
    return private_path, public_path


def test_attestation_sign_verify_and_key_identity(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.txt").write_text("checkpoint evidence\n")
    (bundle / "SHA256SUMS").write_text("checksum listing\n")
    private, public = _keys(tmp_path)

    signed = sign_bundle(bundle, private_key_path=private, key_id="ops-2026-a")
    assert signed.name == ATTESTATION_FILE
    valid, errors = verify_bundle(bundle, public_key_path=public, expected_key_id="ops-2026-a")
    assert valid and not errors
    valid, errors = verify_bundle(bundle, public_key_path=public, expected_key_id="untrusted")
    assert not valid
    assert "key_id" in " ".join(errors)


def test_attestation_detects_content_and_inventory_changes(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    evidence = bundle / "journal.txt"
    evidence.write_text("safe log")
    private, public = _keys(tmp_path)
    sign_bundle(bundle, private_key_path=private, key_id="k1")

    evidence.write_text("tampered log")
    valid, errors = verify_bundle(bundle, public_key_path=public)
    assert not valid
    assert "content hash" in " ".join(errors)


def test_attestation_refuses_overwrite(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "evidence.txt").write_text("evidence")
    private, _ = _keys(tmp_path)
    sign_bundle(bundle, private_key_path=private, key_id="k1")
    with pytest.raises(FileExistsError):
        sign_bundle(bundle, private_key_path=private, key_id="k1")


def test_attestation_rejects_symlinked_evidence(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (bundle / "linked.txt").symlink_to(outside)
    private, _ = _keys(tmp_path)
    with pytest.raises(ValueError, match="symlinks"):
        sign_bundle(bundle, private_key_path=private, key_id="k1")
