from __future__ import annotations

from datetime import datetime

from .models import Experience, Trajectory


def reconstruct_trajectory(
    trajectory_id: str,
    experiences: tuple[Experience, ...],
    *,
    status: str = "active",
) -> Trajectory:
    ordered = tuple(sorted(
        (e for e in experiences if e.trajectory_id == trajectory_id),
        key=lambda e: (e.occurred_at, e.id),
    ))
    if not ordered:
        raise ValueError("cannot reconstruct empty trajectory")
    return Trajectory(
        id=trajectory_id,
        experience_ids=tuple(e.id for e in ordered),
        started_at=ordered[0].occurred_at,
        ended_at=ordered[-1].occurred_at if status != "active" else None,
        status=status,
    )


def validate_experience_temporal_order(experiences: tuple[Experience, ...]) -> None:
    ordered = sorted(experiences, key=lambda e: (e.occurred_at, e.id))
    for previous, current in zip(ordered, ordered[1:]):
        if current.occurred_at < previous.occurred_at:
            raise ValueError("experience temporal order is invalid")
