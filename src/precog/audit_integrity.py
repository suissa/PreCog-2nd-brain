from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .promotion_audit import PromotionAuditEvent

GENESIS_HASH = "0" * 64


def canonical_event(event: PromotionAuditEvent) -> str:
    """Serialize every decision field deterministically for integrity hashing."""
    payload = {
        "id": event.id,
        "candidate_id": event.candidate_id,
        "candidate_version": event.candidate_version,
        "candidate_provenance": list(event.candidate_provenance),
        "baseline_candidate_id": event.baseline_candidate_id,
        "promoted": event.promoted,
        "reason": event.reason,
        "candidate_quality": event.candidate_quality,
        "baseline_quality": event.baseline_quality,
        "sample_count": event.sample_count,
        "evaluated_experience_ids": list(event.evaluated_experience_ids),
        "behavior_accuracy": event.behavior_accuracy,
        "successful_outcome_rate": event.successful_outcome_rate,
        "brier_score": event.brier_score,
        "evidence_coverage": event.evidence_coverage,
        "guardrail_failures": list(event.guardrail_failures),
        "recorded_at": event.recorded_at.isoformat(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def calculate_event_hash(event: PromotionAuditEvent, previous_hash: str) -> str:
    if len(previous_hash) != 64 or any(c not in "0123456789abcdef" for c in previous_hash):
        raise ValueError("previous_hash must be a lowercase SHA-256 hex digest")
    material = previous_hash + "\n" + canonical_event(event)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PromotionAuditIntegrityReport:
    valid: bool
    checked_events: int
    legacy_unhashed_events: int
    errors: tuple[str, ...]
    verified_head_hash: str


def verify_chain(
    rows: tuple[tuple[PromotionAuditEvent, str | None, str | None], ...],
    *,
    expected_head_hash: str,
) -> PromotionAuditIntegrityReport:
    """Verify chained rows in sequence order; unhashed pre-migration rows are reported."""
    previous_hash = GENESIS_HASH
    checked = 0
    legacy = 0
    errors: list[str] = []
    for event, stored_previous, stored_hash in rows:
        if stored_hash is None or stored_previous is None:
            legacy += 1
            continue
        if stored_previous != previous_hash:
            errors.append(f"{event.id}: previous hash does not match the preceding event")
        calculated = calculate_event_hash(event, stored_previous)
        if calculated != stored_hash:
            errors.append(f"{event.id}: event hash does not match its content")
        previous_hash = stored_hash
        checked += 1
    if previous_hash != expected_head_hash:
        errors.append("chain head does not match the last verified event hash")
    return PromotionAuditIntegrityReport(
        valid=not errors,
        checked_events=checked,
        legacy_unhashed_events=legacy,
        errors=tuple(errors),
        verified_head_hash=previous_hash,
    )
