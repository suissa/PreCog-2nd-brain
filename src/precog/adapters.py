from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


class ModelAdapterError(Exception):
    """Typed, recoverable provider failure."""


class ProviderTimeout(ModelAdapterError):
    pass


class ProviderMalformedResponse(ModelAdapterError):
    pass


class ProviderHTTPError(ModelAdapterError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be >= 0")


class ExtractionAdapter(Protocol):
    def extract(self, text: str) -> Mapping[str, Any]: ...


class SummarizationAdapter(Protocol):
    def summarize(self, text: str) -> str: ...


class ReflectionAdapter(Protocol):
    def reflect(self, context: str) -> str: ...


class RCAAdapter(Protocol):
    def analyze(self, context: str) -> Mapping[str, Any]: ...


class EmbeddingAdapter(Protocol):
    @property
    def model(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def dimensions(self) -> int: ...
    def embed(self, text: str) -> Sequence[float]: ...


class RerankingAdapter(Protocol):
    def rerank(self, candidates: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]: ...


class PredictionAdapter(Protocol):
    def predict(self, context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class MockModelAdapter:
    """Provider-free adapter for deterministic tests and local execution."""
    response: Any
    model: str = "mock"
    version: str = "1"

    def extract(self, text: str) -> Mapping[str, Any]:
        return {"text": text, "response": self.response}

    def summarize(self, text: str) -> str:
        return str(self.response)

    def reflect(self, context: str) -> str:
        return str(self.response)

    def analyze(self, context: str) -> Mapping[str, Any]:
        return {"analysis": self.response}

    @property
    def dimensions(self) -> int:
        if isinstance(self.response, Sequence) and not isinstance(self.response, (str, bytes)):
            return len(self.response)
        return 1

    def embed(self, text: str) -> Sequence[float]:
        if isinstance(self.response, Sequence) and not isinstance(self.response, (str, bytes)):
            return tuple(float(x) for x in self.response)
        return (1.0,)

    def rerank(self, candidates: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
        return tuple(candidates)

    def predict(self, context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        if isinstance(self.response, Sequence) and not isinstance(self.response, (str, bytes, Mapping)):
            return tuple(self.response)
        return ({"prediction": self.response},)


class OpenAICompatibleHTTPAdapter:
    """Minimal vendor-neutral JSON adapter for OpenAI-compatible HTTP endpoints.

    The core domain knows only adapter protocols. Endpoint, API key and model
    are runtime configuration and never persisted in domain entities.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        retry_policy: RetryPolicy | None = None,
        opener: Any = urllib.request.urlopen,
    ) -> None:
        if not base_url or not api_key or not model:
            raise ValueError("base_url, api_key and model are required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self._opener = opener

    @property
    def version(self) -> str:
        return "openai-compatible-v1"

    @property
    def dimensions(self) -> int:
        raise ProviderMalformedResponse("embedding dimensions are response-dependent")

    def _request(self, operation: str, payload: Mapping[str, Any]) -> Any:
        body = json.dumps({"model": self.model, **payload}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/{operation}",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        last: Exception | None = None
        for attempt in range(self.retry_policy.max_attempts):
            try:
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    raw = response.read()
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, Mapping):
                    raise ProviderMalformedResponse("provider response must be an object")
                return data
            except urllib.error.HTTPError as exc:
                last = ProviderHTTPError(exc.code, f"provider HTTP error: {exc.code}")
                if exc.code < 500:
                    raise last
            except (TimeoutError, urllib.error.URLError) as exc:
                last = ProviderTimeout(str(exc))
            except (json.JSONDecodeError, UnicodeDecodeError, ProviderMalformedResponse) as exc:
                raise ProviderMalformedResponse(str(exc))
            if attempt + 1 < self.retry_policy.max_attempts and self.retry_policy.backoff_seconds:
                time.sleep(self.retry_policy.backoff_seconds * (attempt + 1))
        raise last or ModelAdapterError("provider request failed")

    @staticmethod
    def _content(data: Mapping[str, Any]) -> str:
        try:
            value = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderMalformedResponse("missing choices[0].message.content") from exc
        if not isinstance(value, str):
            raise ProviderMalformedResponse("message content must be a string")
        return value

    def summarize(self, text: str) -> str:
        return self._content(self._request("chat/completions", {
            "messages": [{"role": "user", "content": text}],
        }))

    def reflect(self, context: str) -> str:
        return self.summarize(context)

    def extract(self, text: str) -> Mapping[str, Any]:
        return {"text": self.summarize(text)}

    def analyze(self, context: str) -> Mapping[str, Any]:
        return {"analysis": self.summarize(context)}

    def predict(self, context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        content = self.summarize(json.dumps(dict(context), sort_keys=True))
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderMalformedResponse("prediction content must be JSON") from exc
        if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
            raise ProviderMalformedResponse("prediction response must be a list of objects")
        return tuple(value)

    def rerank(self, candidates: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
        content = self.summarize(json.dumps(list(candidates), sort_keys=True))
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderMalformedResponse("rerank content must be JSON") from exc
        if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
            raise ProviderMalformedResponse("rerank response must be a list of objects")
        return tuple(value)

    def embed(self, text: str) -> Sequence[float]:
        data = self._request("embeddings", {"input": text})
        try:
            vector = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderMalformedResponse("missing data[0].embedding") from exc
        if not isinstance(vector, Sequence) or isinstance(vector, (str, bytes)):
            raise ProviderMalformedResponse("embedding must be an array")
        try:
            return tuple(float(x) for x in vector)
        except (TypeError, ValueError) as exc:
            raise ProviderMalformedResponse("embedding values must be numeric") from exc
