from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class DataClass(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PII = "pii"
    SECRET = "secret"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class FieldPolicy:
    field: str
    classification: DataClass
    retain: bool = True
    embed: bool = False
    trace: bool = False


@dataclass(frozen=True, slots=True)
class PrivacyPolicy:
    fields: tuple[FieldPolicy, ...]

    def policy_for(self, field: str) -> FieldPolicy | None:
        return next((p for p in self.fields if p.field == field), None)

    def sanitize_for_embedding(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in payload.items():
            policy = self.policy_for(key)
            if policy and (policy.classification in {DataClass.PII, DataClass.SECRET, DataClass.RESTRICTED} or not policy.embed):
                continue
            result[key] = value
        return result

    def sanitize_for_trace(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in payload.items():
            policy = self.policy_for(key)
            if policy and (policy.classification in {DataClass.PII, DataClass.SECRET, DataClass.RESTRICTED} or not policy.trace):
                continue
            result[key] = value
        return result


def validate_temporal_interval(valid_from: Any, valid_to: Any) -> None:
    if valid_from is not None and valid_to is not None and valid_to < valid_from:
        raise ValueError("valid_to must not precede valid_from")


def validate_migration_version(version: int, current: int) -> None:
    if version != current + 1:
        raise ValueError("migrations must advance exactly one schema version")
