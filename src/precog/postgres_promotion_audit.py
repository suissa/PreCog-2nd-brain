from __future__ import annotations

import json
from typing import Any

from .audit_integrity import GENESIS_HASH, PromotionAuditIntegrityReport, calculate_event_hash, verify_chain
from .promotion_audit import PromotionAuditEvent, PromotionAuditWriter


class PostgresPromotionAuditLog(PromotionAuditWriter):
    """Durable append-only audit sink with a serialized SHA-256 event chain.

    Apply migrations 002 and 003 before use. The chain state row serializes
    concurrent appends; integrity checks are read-only and never authorize promotion.
    """

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def append(self, event: PromotionAuditEvent) -> bool:
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "SELECT last_hash FROM promotion_audit_chain_state WHERE singleton = TRUE FOR UPDATE"
                )
                state = cursor.fetchone()
                if state is None:
                    raise RuntimeError("promotion audit chain state is missing; apply migration 003")
                previous_hash = state[0]
                cursor.execute(
                    """SELECT event_id, candidate_id, candidate_version,
                        candidate_provenance, baseline_candidate_id, promoted, reason,
                        candidate_quality, baseline_quality, sample_count,
                        evaluated_experience_ids, behavior_accuracy,
                        successful_outcome_rate, brier_score, evidence_coverage,
                        guardrail_failures, recorded_at
                        FROM promotion_audit WHERE event_id = %s""",
                    (event.id,),
                )
                existing_row = cursor.fetchone()
                if existing_row is not None:
                    existing = self._event_from_row(existing_row)
                    if existing != event:
                        raise ValueError("promotion audit event ID reused with conflicting content")
                    self._connection.commit()
                    return False

                event_hash = calculate_event_hash(event, previous_hash)
                cursor.execute(
                    """INSERT INTO promotion_audit (
                        event_id, candidate_id, candidate_version, candidate_provenance,
                        baseline_candidate_id, promoted, reason, candidate_quality,
                        baseline_quality, sample_count, evaluated_experience_ids,
                        behavior_accuracy, successful_outcome_rate, brier_score,
                        evidence_coverage, guardrail_failures, recorded_at,
                        previous_hash, event_hash
                    ) VALUES (
                        %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s, %s, %s::jsonb, %s, %s, %s
                    )""",
                    (
                        event.id, event.candidate_id, event.candidate_version,
                        self._json(event.candidate_provenance), event.baseline_candidate_id,
                        event.promoted, event.reason, event.candidate_quality,
                        event.baseline_quality, event.sample_count,
                        self._json(event.evaluated_experience_ids), event.behavior_accuracy,
                        event.successful_outcome_rate, event.brier_score,
                        event.evidence_coverage, self._json(event.guardrail_failures),
                        event.recorded_at, previous_hash, event_hash,
                    ),
                )
                cursor.execute(
                    """UPDATE promotion_audit_chain_state SET last_hash = %s
                        WHERE singleton = TRUE""",
                    (event_hash,),
                )
            self._connection.commit()
            return True
        except Exception:
            self._connection.rollback()
            raise

    def list_events(self, *, limit: int = 1000) -> tuple[PromotionAuditEvent, ...]:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT event_id, candidate_id, candidate_version,
                    candidate_provenance, baseline_candidate_id, promoted, reason,
                    candidate_quality, baseline_quality, sample_count,
                    evaluated_experience_ids, behavior_accuracy,
                    successful_outcome_rate, brier_score, evidence_coverage,
                    guardrail_failures, recorded_at
                    FROM promotion_audit
                    ORDER BY audit_sequence LIMIT %s""",
                (limit,),
            )
            rows = cursor.fetchall()
        self._connection.commit()
        return tuple(self._event_from_row(row) for row in rows)

    def verify_integrity(self) -> PromotionAuditIntegrityReport:
        """Verify all chained events and compare the computed head with persisted state."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT event_id, candidate_id, candidate_version,
                    candidate_provenance, baseline_candidate_id, promoted, reason,
                    candidate_quality, baseline_quality, sample_count,
                    evaluated_experience_ids, behavior_accuracy,
                    successful_outcome_rate, brier_score, evidence_coverage,
                    guardrail_failures, recorded_at, previous_hash, event_hash
                    FROM promotion_audit ORDER BY audit_sequence"""
            )
            raw_rows = cursor.fetchall()
            cursor.execute(
                "SELECT last_hash FROM promotion_audit_chain_state WHERE singleton = TRUE"
            )
            state = cursor.fetchone()
        self._connection.commit()
        if state is None:
            return PromotionAuditIntegrityReport(
                valid=False, checked_events=0, legacy_unhashed_events=0,
                errors=("promotion audit chain state is missing",),
                verified_head_hash=GENESIS_HASH,
            )
        rows = tuple(
            (self._event_from_row(tuple(row[:17])), row[17], row[18])
            for row in raw_rows
        )
        return verify_chain(rows, expected_head_hash=state[0])

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)

    @staticmethod
    def _decode(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @classmethod
    def _event_from_row(cls, row: tuple[Any, ...]) -> PromotionAuditEvent:
        return PromotionAuditEvent(
            id=row[0], candidate_id=row[1], candidate_version=row[2],
            candidate_provenance=tuple(cls._decode(row[3])), baseline_candidate_id=row[4],
            promoted=row[5], reason=row[6], candidate_quality=float(row[7]),
            baseline_quality=float(row[8]) if row[8] is not None else None,
            sample_count=row[9], evaluated_experience_ids=tuple(cls._decode(row[10])),
            behavior_accuracy=float(row[11]), successful_outcome_rate=float(row[12]),
            brier_score=float(row[13]), evidence_coverage=float(row[14]),
            guardrail_failures=tuple(cls._decode(row[15])), recorded_at=row[16],
        )
