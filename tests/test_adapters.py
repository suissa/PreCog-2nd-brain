from __future__ import annotations

import json
import urllib.error

import pytest

from precog.adapters import (
    MockModelAdapter,
    OpenAICompatibleHTTPAdapter,
    ProviderMalformedResponse,
    ProviderTimeout,
    RetryPolicy,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def test_mock_adapter_supports_all_capabilities():
    adapter = MockModelAdapter(response=[0.1, 0.2])
    assert adapter.extract("x")["text"] == "x"
    assert adapter.summarize("x") == "[0.1, 0.2]"
    assert adapter.reflect("x")
    assert adapter.analyze("x")["analysis"] == [0.1, 0.2]
    assert tuple(adapter.embed("x")) == (0.1, 0.2)
    assert adapter.rerank(({"id": "a"},)) == ({"id": "a"},)


def test_http_adapter_success_and_provider_swap():
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, request.get_header("Authorization"), timeout))
        return FakeResponse({"choices": [{"message": {"content": "summary"}}]})

    adapter = OpenAICompatibleHTTPAdapter(
        base_url="https://provider-a.example",
        api_key="secret",
        model="model-a",
        opener=opener,
    )
    assert adapter.summarize("hello") == "summary"
    assert calls[0][0].endswith("/v1/chat/completions")
    assert calls[0][1] == "Bearer secret"

    other = OpenAICompatibleHTTPAdapter(
        base_url="https://provider-b.example",
        api_key="secret",
        model="model-b",
        opener=opener,
    )
    assert other.model != adapter.model


def test_http_adapter_malformed_response_is_typed():
    def opener(request, timeout):
        return FakeResponse({"choices": []})

    adapter = OpenAICompatibleHTTPAdapter(
        base_url="https://provider.example",
        api_key="secret",
        model="model",
        opener=opener,
    )
    with pytest.raises(ProviderMalformedResponse):
        adapter.summarize("hello")


def test_http_adapter_timeout_is_typed_and_retryable():
    attempts = []

    def opener(request, timeout):
        attempts.append(1)
        raise TimeoutError("timed out")

    adapter = OpenAICompatibleHTTPAdapter(
        base_url="https://provider.example",
        api_key="secret",
        model="model",
        retry_policy=RetryPolicy(max_attempts=3),
        opener=opener,
    )
    with pytest.raises(ProviderTimeout):
        adapter.summarize("hello")
    assert len(attempts) == 3


def test_http_adapter_retries_server_errors():
    attempts = []

    def opener(request, timeout):
        attempts.append(1)
        if len(attempts) < 2:
            raise urllib.error.HTTPError(request.full_url, 503, "unavailable", {}, None)
        return FakeResponse({"choices": [{"message": {"content": "ok"}}]})

    adapter = OpenAICompatibleHTTPAdapter(
        base_url="https://provider.example",
        api_key="secret",
        model="model",
        retry_policy=RetryPolicy(max_attempts=2),
        opener=opener,
    )
    assert adapter.summarize("hello") == "ok"
    assert len(attempts) == 2


def test_http_embedding_validates_shape_and_values():
    def opener(request, timeout):
        return FakeResponse({"data": [{"embedding": [1, 2.5, 3]}]})

    adapter = OpenAICompatibleHTTPAdapter(
        base_url="https://provider.example",
        api_key="secret",
        model="embedding-model",
        opener=opener,
    )
    assert tuple(adapter.embed("hello")) == (1.0, 2.5, 3.0)
    with pytest.raises(ProviderMalformedResponse):
        OpenAICompatibleHTTPAdapter(
            base_url="https://provider.example",
            api_key="secret",
            model="model",
            opener=lambda request, timeout: FakeResponse({"data": [{}]}),
        ).embed("hello")
