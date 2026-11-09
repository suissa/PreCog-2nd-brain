import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.anchor_service import AnchorConflict, MonotonicAnchor, PublisherUnauthorized, canonical_json


def signed_publish(key, sequence, digest, request_id="req", key_id="publisher-1"):
    payload = {"version": 1, "sequence": sequence, "registry_sha256": digest,
               "request_id": request_id, "publisher_key_id": key_id}
    return {**payload, "signature": base64.b64encode(key.sign(canonical_json(payload))).decode()}


@pytest.fixture
def authority(tmp_path: Path):
    publisher = Ed25519PrivateKey.generate()
    response = Ed25519PrivateKey.generate()
    service = MonotonicAnchor(tmp_path / "anchor.db", response, {"publisher-1": publisher.public_key()})
    return service, publisher, response


def test_publish_and_signed_head(authority):
    service, publisher, response = authority
    digest = "a" * 64
    service.publish(signed_publish(publisher, 1, digest))
    envelope = service.signed_head("fresh-nonce")
    response.public_key().verify(base64.b64decode(envelope["signature"]), canonical_json(envelope["payload"]))
    assert envelope["payload"] == {"version": 1, "sequence": 1, "registry_sha256": digest, "nonce": "fresh-nonce"}


def test_rejects_rollback_and_same_sequence_conflict(authority):
    service, publisher, _ = authority
    service.publish(signed_publish(publisher, 3, "a" * 64))
    with pytest.raises(AnchorConflict):
        service.publish(signed_publish(publisher, 2, "b" * 64, "older"))
    with pytest.raises(AnchorConflict):
        service.publish(signed_publish(publisher, 3, "b" * 64, "conflict"))


def test_publisher_signature_is_mandatory(authority):
    service, publisher, _ = authority
    req = signed_publish(publisher, 1, "a" * 64)
    req["signature"] = base64.b64encode(b"invalid").decode()
    with pytest.raises(PublisherUnauthorized):
        service.publish(req)


def test_request_idempotency(authority):
    service, publisher, _ = authority
    req = signed_publish(publisher, 1, "a" * 64, "stable")
    assert service.publish(req)["idempotent"] is False
    assert service.publish(req)["idempotent"] is True
    with pytest.raises(AnchorConflict):
        service.publish(signed_publish(publisher, 2, "b" * 64, "stable"))


def test_concurrent_conflicting_checkpoints_only_one_wins(authority):
    service, publisher, _ = authority
    requests = [
        signed_publish(publisher, 1, hashlib.sha256(str(n).encode()).hexdigest(), f"r{n}")
        for n in (1, 2)
    ]
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda req: _attempt(service, req), requests))
    assert sum(result == "ok" for result in results) == 1
    assert sum(result == "conflict" for result in results) == 1


def _attempt(service, request):
    try:
        service.publish(request)
        return "ok"
    except AnchorConflict:
        return "conflict"


def test_publisher_rotation_and_revocation(tmp_path: Path):
    old_key = Ed25519PrivateKey.generate()
    new_key = Ed25519PrivateKey.generate()
    response = Ed25519PrivateKey.generate()
    service = MonotonicAnchor(
        tmp_path / "rotated.db", response,
        {"publisher-old": old_key.public_key(), "publisher-new": new_key.public_key()},
        publisher_status={"publisher-old": "retired", "publisher-new": "active"},
    )
    with pytest.raises(PublisherUnauthorized, match="retired"):
        service.publish(signed_publish(old_key, 1, "a" * 64, "old", "publisher-old"))
    accepted = signed_publish(new_key, 1, "b" * 64, "new", "publisher-new")
    assert service.publish(accepted)["idempotent"] is False
    revoked = MonotonicAnchor(
        tmp_path / "revoked.db", response, {"publisher-old": old_key.public_key()},
        publisher_status={"publisher-old": "revoked"},
    )
    with pytest.raises(PublisherUnauthorized, match="revoked"):
        revoked.publish(signed_publish(old_key, 1, "c" * 64, "revoked", "publisher-old"))


def test_audit_chain_verifies_and_detects_rewritten_history(authority):
    service, publisher, _ = authority
    service.publish(signed_publish(publisher, 1, "a" * 64, "first"))
    service.publish(signed_publish(publisher, 2, "b" * 64, "second"))
    report = service.verify_audit_chain()
    assert report["valid"] is True
    assert report["event_count"] == 2
    assert len(report["head_hash"]) == 64

    with service._connect() as conn:
        conn.execute("DROP TRIGGER anchor_publish_log_no_update")
        conn.execute("UPDATE anchor_publish_log SET registry_sha256=? WHERE request_id=?",
                     ("f" * 64, "first"))
    with pytest.raises(AnchorConflict, match="audit chain integrity"):
        service.verify_audit_chain()
    with pytest.raises(AnchorConflict, match="audit chain integrity"):
        service.signed_head("fresh-after-tamper")
