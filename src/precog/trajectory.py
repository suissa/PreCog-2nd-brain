from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import Experience, Trajectory


@dataclass(frozen=True, slots=True)
class TrajectoryReconstruction:
    trajectory: Trajectory
    missing_experience_ids: tuple[str, ...] = ()
    duplicate_experience_ids: tuple[str, ...] = ()
    reordered: bool = False

    @property
    def has_gaps(self) -> bool:
        return bool(self.missing_experience_ids)


def reconstruct_trajectory_diagnostics(
    trajectory_id: str,
    experiences: tuple[Experience, ...],
    *,
    expected_experience_ids: tuple[str, ...] | None = None,
    status: str = "active",
) -> TrajectoryReconstruction:
    selected = tuple(e for e in experiences if e.trajectory_id == trajectory_id)
    if not selected:
        raise ValueError("cannot reconstruct empty trajectory")

    input_ids = tuple(e.id for e in selected)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for experience_id in input_ids:
        if experience_id in seen:
            duplicates.add(experience_id)
        seen.add(experience_id)

    ordered = tuple(sorted(selected, key=lambda e: (e.occurred_at, e.id)))
    ordered_ids = tuple(e.id for e in ordered)
    missing = ()
    if expected_experience_ids is not None:
        expected = tuple(dict.fromkeys(expected_experience_ids))
        missing = tuple(i for i in expected if i not in seen)

    trajectory = Trajectory(
        id=trajectory_id,
        experience_ids=ordered_ids,
        started_at=ordered[0].occurred_at,
        ended_at=ordered[-1].occurred_at if status != "active" else None,
        status=status,
    )
    return TrajectoryReconstruction(
        trajectory=trajectory,
        missing_experience_ids=missing,
        duplicate_experience_ids=tuple(sorted(duplicates)),
        reordered=input_ids != ordered_ids,
    )


def reconstruct_trajectory(
    trajectory_id: str,
    experiences: tuple[Experience, ...],
    *,
    expected_experience_ids: tuple[str, ...] | None = None,
    status: str = "active",
) -> Trajectory:
    report = reconstruct_trajectory_diagnostics(
        trajectory_id,
        experiences,
        expected_experience_ids=expected_experience_ids,
        status=status,
    )
    if report.missing_experience_ids:
        raise ValueError(
            "trajectory reconstruction has missing experiences: "
            + ", ".join(report.missing_experience_ids)
        )
    if report.duplicate_experience_ids:
        raise ValueError(
            "trajectory reconstruction has duplicate experiences: "
            + ", ".join(report.duplicate_experience_ids)
        )
    return report.trajectory


def validate_experience_temporal_order(experiences: tuple[Experience, ...]) -> None:
    ordered = sorted(experiences, key=lambda e: (e.occurred_at, e.id))
    for previous, current in zip(ordered, ordered[1:]):
        if current.occurred_at < previous.occurred_at:
            raise ValueError("experience temporal order is invalid")
