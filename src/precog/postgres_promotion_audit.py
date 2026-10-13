from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .promotion_audit import PromotionAuditEvent, PromotionAuditWriter


class PostgresPromotionAuditLog(PromotionAuditWriter):
    """Durable append-only promotion audit sink using a DB-API connection.

    Apply sql/002_promotion_audit.sql before use. The database migration installs
    a trigger that rejects UPDATE and DELETE operations on audit rows.
    """

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def append(self, event: PromotionAuditEvent) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO promotion_audit (
                    event_id, candidate_id, candidate_version, candidate_provenance,
                    baseline_candidate_id, promoted, reason, candidate_quality,
                    baseline_quality, sample_count, evaluated_experience_ids,
                    behavior_accuracy, successful_outcome_rate, brier_score,
                    evidence_coverage, guardrail_failures, recorded_at
                ) VALUES (
                    %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s::jsonb,
                    %s, %s, %s, %s, %s::jsonb, %s
                ) ON CONFLICT (event_id) DO NOTHING RETURNING event_id""",
                (
                    event.id,
                    event.candidate_id,
                    event.candidate_version,
                    self._json(event.candidate_provenance),
                    event.baseline_candidate_id,
                    event.promoted,
                    event.reason,
                    event.candidate_quality,
                    event.baseline_quality,
                    event.sample_count,
                    self._json(event.evaluated_experience_ids),
                    event.behavior_accuracy,
                    event.successful_outcome_rate,
                    event.brier_score,
                    event.evidence_coverage,
                    self._json(event.guardrail_failures),
                    event.recorded_at,
                ),
            )
            inserted = cursor.fetchone()
            if inserted is not None:
                self._connection.commit()
                return True

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
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("promotion audit conflict row disappeared")
        existing = self._event_from_row(row)
        if existing != event:
            raise ValueError("promotion audit event ID reused with conflicting content")
        return False

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
                    ORDER BY recorded_at, event_id LIMIT %s""",
                (limit,),
            )
            rows = cursor.fetchall()
        return tuple(self._event_from_row(row) for row in rows)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)

    @staticmethod
    def _decode(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @classmethod
    def _event_from_row(cls, row: tuple[Any, ...]) -> PromotionAuditEvent:
        return PromotionAuditEvent(
            id=row[0],
            candidate_id=row[1],
            candidate_version=row[2],
            candidate_provenance=tuple(cls._decode(row[3])),
            baseline_candidate_id=row[4],
            promoted=row[5],
            reason=row[6],
            candidate_quality=float(row[7]),
            baseline_quality=float(row[8]) if row[8] is not None else None,
            sample_count=row[9],
            evaluated_experience_ids=tuple(cls._decode(row[10])),
            behavior_accuracy=float(row[11]),
            successful_outcome_rate=float(row[12]),
            brier_score=float(row[13]),
            evidence_coverage=float(row[14]),
            guardrail_failures=tuple(cls._decode(row[15])),
            recorded_at=row[16],
        )
