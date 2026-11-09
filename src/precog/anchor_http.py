"""Minimal WSGI transport for the monotonic anchor authority."""
from __future__ import annotations

import json
from typing import Callable, Iterable
from urllib.parse import parse_qs

from precog.anchor_service import AnchorConflict, MonotonicAnchor, PublisherUnauthorized

_START_RESPONSE = Callable[[str, list[tuple[str, str]]], object]
_BODY_LIMIT = 16 * 1024


class AnchorWSGIApp:
    """Expose signed head reads and publisher-authenticated checkpoint writes.

    TLS must terminate in a trusted front proxy which sets wsgi.url_scheme=https.
    Do not expose this app directly on an untrusted network.
    """

    def __init__(self, authority: MonotonicAnchor, *, require_https: bool = True) -> None:
        self.authority = authority
        self.require_https = require_https

    @staticmethod
    def _json(start_response: _START_RESPONSE, status: str, payload: dict[str, object]) -> list[bytes]:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        start_response(status, [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("Pragma", "no-cache"),
            ("X-Content-Type-Options", "nosniff"),
        ])
        return [body]

    def __call__(self, environ: dict[str, object], start_response: _START_RESPONSE) -> Iterable[bytes]:
        if self.require_https and environ.get("wsgi.url_scheme") != "https":
            return self._json(start_response, "400 Bad Request", {"error": "https_required"})
        method = str(environ.get("REQUEST_METHOD", ""))
        path = str(environ.get("PATH_INFO", ""))
        if path == "/v1/trust-registry/head":
            if method != "GET":
                return self._json(start_response, "405 Method Not Allowed", {"error": "method_not_allowed"})
            try:
                query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True, strict_parsing=True)
            except ValueError:
                return self._json(start_response, "400 Bad Request", {"error": "malformed_query"})
            nonces = query.get("nonce", [])
            if set(query) != {"nonce"} or len(nonces) != 1:
                return self._json(start_response, "400 Bad Request", {"error": "exactly_one_nonce_required"})
            try:
                return self._json(start_response, "200 OK", self.authority.signed_head(nonces[0]))
            except ValueError:
                return self._json(start_response, "400 Bad Request", {"error": "invalid_nonce"})
            except LookupError:
                return self._json(start_response, "503 Service Unavailable", {"error": "anchor_uninitialized"})
        if path == "/v1/trust-registry/checkpoints":
            if method != "POST":
                return self._json(start_response, "405 Method Not Allowed", {"error": "method_not_allowed"})
            if str(environ.get("CONTENT_TYPE", "")).split(";", 1)[0].strip().lower() != "application/json":
                return self._json(start_response, "415 Unsupported Media Type", {"error": "application_json_required"})
            try:
                length = int(str(environ.get("CONTENT_LENGTH", "")))
            except ValueError:
                return self._json(start_response, "400 Bad Request", {"error": "content_length_required"})
            if length < 0:
                return self._json(start_response, "400 Bad Request", {"error": "invalid_content_length"})
            if length > _BODY_LIMIT:
                return self._json(start_response, "413 Content Too Large", {"error": "request_too_large"})
            stream = environ.get("wsgi.input")
            if stream is None or not hasattr(stream, "read"):
                return self._json(start_response, "400 Bad Request", {"error": "request_body_required"})
            raw = stream.read(length)  # type: ignore[union-attr]
            if len(raw) != length:
                return self._json(start_response, "400 Bad Request", {"error": "incomplete_request_body"})
            try:
                request = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._json(start_response, "400 Bad Request", {"error": "invalid_json"})
            if not isinstance(request, dict):
                return self._json(start_response, "400 Bad Request", {"error": "json_object_required"})
            try:
                result = self.authority.publish(request)
                return self._json(start_response, "200 OK", result)
            except PublisherUnauthorized:
                return self._json(start_response, "401 Unauthorized", {"error": "publisher_unauthorized"})
            except AnchorConflict:
                return self._json(start_response, "409 Conflict", {"error": "checkpoint_conflict"})
        return self._json(start_response, "404 Not Found", {"error": "not_found"})
