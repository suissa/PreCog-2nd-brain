from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .audit_checkpoint import (
    PromotionAuditCheckpoint,
    PromotionAuditReconciliation,
    create_checkpoint,
    reconcile_checkpoint as reconcile_external_checkpoint,
)

from .audit_integrity import GENESIS_HASH, PromotionAuditIntegrityReport, calculate_event_hash, verify_chain
from .promotion_audit import PromotionAuditEvent, PromotionAuditWriter


class PostgresPromotionAuditLog(PromotionAuditWriter):
    """Durable append-only audit sink with a serialized SHA-256 event chain."""

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

    def latest_checkpoint_position(self) -> tuple[int, str]:
        """Return the latest sequence and its hash for an external signed checkpoint."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT audit_sequence, event_hash
                    FROM promotion_audit
                    WHERE event_hash IS NOT NULL
                    ORDER BY audit_sequence DESC LIMIT 1"""
            )
            row = cursor.fetchone()
        self._connection.commit()
        if row is None:
            return 0, GENESIS_HASH
        return int(row[0]), str(row[1])

    def hash_at_sequence(self, sequence: int) -> str | None:
        """Read the event hash anchored by an external checkpoint sequence."""
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        if sequence == 0:
            return GENESIS_HASH
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT event_hash FROM promotion_audit WHERE audit_sequence = %s",
                (sequence,),
            )
            row = cursor.fetchone()
        self._connection.commit()
        return None if row is None or row[0] is None else str(row[0])

    def export_checkpoint(
        self,
        *,
        private_key: Any,
        public_key_id: str,
        created_at: datetime | None = None,
    ) -> PromotionAuditCheckpoint:
        """Create a signed checkpoint for the current verified hash-chain head.

        Store the returned JSON outside the database (and preferably outside the
        database administrator's control). This method never writes the checkpoint
        to PostgreSQL.
        """
        report = self.verify_integrity()
        if not report.valid:
            raise ValueError("cannot export checkpoint for an invalid audit chain")
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT audit_sequence, event_hash FROM promotion_audit
                    WHERE event_hash IS NOT NULL
                    ORDER BY audit_sequence DESC LIMIT 1"""
            )
            row = cursor.fetchone()
        self._connection.commit()
        sequence = int(row[0]) if row is not None else 0
        stored_head = row[1] if row is not None else GENESIS_HASH
        if stored_head != report.verified_head_hash:
            raise RuntimeError("audit chain head changed while creating checkpoint")
        return create_checkpoint(
            report,
            sequence=sequence,
            private_key=private_key,
            public_key_id=public_key_id,
            created_at=created_at,
        )

    def reconcile_checkpoint(
        self,
        checkpoint: PromotionAuditCheckpoint,
        *,
        public_key: Any,
    ) -> PromotionAuditReconciliation:
        """Compare the local verified chain against a checkpoint stored externally."""
        report = self.verify_integrity()
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT audit_sequence, event_hash FROM promotion_audit
                    WHERE event_hash IS NOT NULL
                    ORDER BY audit_sequence DESC LIMIT 1"""
            )
            latest = cursor.fetchone()
            current_sequence = int(latest[0]) if latest is not None else 0
            cursor.execute(
                """SELECT event_hash FROM promotion_audit
                    WHERE audit_sequence = %s""",
                (checkpoint.sequence,),
            ) if checkpoint.sequence > 0 else None
            at_checkpoint = cursor.fetchone() if checkpoint.sequence > 0 else None
        self._connection.commit()
        observed_hash = at_checkpoint[0] if at_checkpoint is not None else (
            GENESIS_HASH if checkpoint.sequence == 0 else None
        )
        return reconcile_external_checkpoint(
            checkpoint,
            public_key=public_key,
            current_report=report,
            current_sequence=current_sequence,
            observed_hash_at_checkpoint=observed_hash,
        )

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
