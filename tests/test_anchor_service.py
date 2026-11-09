import base64
import hashlib
import json
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


def test_concurrent_publishers_only_one_sequence_wins(authority):
    service, publisher, _ = authority
    requests = [signed_publish(publisher, n, hashlib.sha256(str(n).encode()).hexdigest(), f"r{n}") for n in (1, 2)]
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
