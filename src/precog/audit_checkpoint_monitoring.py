"""Operational freshness policy for externally stored audit checkpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .audit_checkpoint import PromotionAuditCheckpoint


def validate_checkpoint_freshness(
    checkpoint: PromotionAuditCheckpoint,
    *,
    current_sequence: int,
    max_age_hours: float = 36,
    max_lag_events: int = 1000,
    now: datetime | None = None,
) -> None:
    """Raise ValueError when a validly signed checkpoint is too old or too far behind.

    Freshness is an operational policy, separate from signature/chain validity.
    Events appended after a checkpoint are normal until the configured lag budget
    is exceeded; they are not classified as tampering by this function.
    """
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be greater than zero")
    if max_lag_events < 0:
        raise ValueError("max_lag_events must be non-negative")
    if current_sequence < checkpoint.sequence:
        raise ValueError("current audit history is shorter than the external checkpoint")

    try:
        created_at = datetime.fromisoformat(checkpoint.created_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("checkpoint creation timestamp is invalid") from error
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("checkpoint creation timestamp must include a timezone")

    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None or observed_now.utzoffset is None:
        raise ValueError("current time must include a timezone")
    age = observed_now.astimezone(timezone.utc) - created_at.astimezone(timezone.utc)
    if age < timedelta(0):
        raise ValueError("checkpoint creation timestamp is in the future")
    if age > timedelta(hours=max_age_hours):
        raise ValueError(
            f"external audit checkpoint is stale: age={age.total_seconds() / 3600:.2f}h "
            f"exceeds limit={max_age_hours:.2f}h"
        )

    lag = current_sequence - checkpoint.sequence
    if lag > max_lag_events:
        raise ValueError(
            f"external audit checkpoint is behind current history: lag={lag} events "
            f"exceeds limit={max_lag_events}"
        )
