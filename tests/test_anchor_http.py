import base64
import io
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.anchor_http import AnchorWSGIApp
from precog.anchor_service import MonotonicAnchor, canonical_json


def _call(app, method, path, *, query="", body=b"", content_type="", scheme="https"):
    captured = {}
    environ = {
        "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)), "CONTENT_TYPE": content_type,
        "wsgi.url_scheme": scheme, "wsgi.input": io.BytesIO(body),
    }

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response = b"".join(app(environ, start_response))
    return captured, json.loads(response)


def _signed(key, seq=1, digest="a" * 64):
    payload = {"version": 1, "sequence": seq, "registry_sha256": digest,
               "request_id": f"req-{seq}", "publisher_key_id": "publisher"}
    return {**payload, "signature": base64.b64encode(key.sign(canonical_json(payload))).decode()}


def _app(tmp_path: Path):
    publisher = Ed25519PrivateKey.generate()
    response = Ed25519PrivateKey.generate()
    authority = MonotonicAnchor(tmp_path / "anchor.db", response, {"publisher": publisher.public_key()})
    return AnchorWSGIApp(authority), publisher


def test_publish_and_get_signed_head(tmp_path):
    app, publisher = _app(tmp_path)
    body = json.dumps(_signed(publisher)).encode()
    result, payload = _call(app, "POST", "/v1/trust-registry/checkpoints",
                            body=body, content_type="application/json")
    assert result["status"] == "200 OK"
    assert payload["sequence"] == 1
    result, envelope = _call(app, "GET", "/v1/trust-registry/head", query="nonce=abc")
    assert result["status"] == "200 OK"
    assert envelope["payload"]["nonce"] == "abc"
    assert result["headers"]["Cache-Control"] == "no-store"


def test_rejects_plain_http_and_bad_nonce(tmp_path):
    app, _ = _app(tmp_path)
    result, _ = _call(app, "GET", "/v1/trust-registry/head", query="nonce=x", scheme="http")
    assert result["status"] == "400 Bad Request"
    result, _ = _call(app, "GET", "/v1/trust-registry/head", query="nonce=x&nonce=y")
    assert result["status"] == "400 Bad Request"


def test_publish_maps_auth_and_conflict_errors(tmp_path):
    app, publisher = _app(tmp_path)
    bad = _signed(publisher)
    bad["signature"] = base64.b64encode(b"wrong").decode()
    result, _ = _call(app, "POST", "/v1/trust-registry/checkpoints",
                      body=json.dumps(bad).encode(), content_type="application/json")
    assert result["status"] == "401 Unauthorized"
    valid = json.dumps(_signed(publisher)).encode()
    _call(app, "POST", "/v1/trust-registry/checkpoints", body=valid, content_type="application/json")
    conflict = json.dumps(_signed(publisher, digest="b" * 64)).encode()
    result, _ = _call(app, "POST", "/v1/trust-registry/checkpoints",
                      body=conflict, content_type="application/json")
    assert result["status"] == "409 Conflict"


def test_rejects_oversized_body_and_wrong_content_type(tmp_path):
    app, _ = _app(tmp_path)
    result, _ = _call(app, "POST", "/v1/trust-registry/checkpoints",
                      body=b"x" * (16 * 1024 + 1), content_type="application/json")
    assert result["status"] == "413 Content Too Large"
    result, _ = _call(app, "POST", "/v1/trust-registry/checkpoints", body=b"{}", content_type="text/plain")
    assert result["status"] == "415 Unsupported Media Type"


def test_unknown_route_and_method(tmp_path):
    app, _ = _app(tmp_path)
    result, _ = _call(app, "GET", "/unknown")
    assert result["status"] == "404 Not Found"
    result, _ = _call(app, "PUT", "/v1/trust-registry/head")
    assert result["status"] == "405 Method Not Allowed"
