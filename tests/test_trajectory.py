from datetime import datetime, timedelta, timezone

import pytest

from precog.models import Experience, Provenance
from precog.trajectory import reconstruct_trajectory, reconstruct_trajectory_diagnostics

NOW = datetime.now(timezone.utc)


def exp(i: str, offset: int) -> Experience:
    return Experience(
        i, "t1", NOW + timedelta(seconds=offset), NOW,
        "actor", "event", {}, Provenance((i,), "capture"),
    )


def test_reconstruction_is_deterministic_after_out_of_order_input() -> None:
    e1, e2 = exp("e1", 1), exp("e2", 2)
    report = reconstruct_trajectory_diagnostics("t1", (e2, e1))
    assert report.trajectory.experience_ids == ("e1", "e2")
    assert report.reordered is True
    assert report.missing_experience_ids == ()


def test_missing_experience_is_explicitly_reported() -> None:
    e1, e3 = exp("e1", 1), exp("e3", 3)
    report = reconstruct_trajectory_diagnostics(
        "t1", (e1, e3), expected_experience_ids=("e1", "e2", "e3")
    )
    assert report.missing_experience_ids == ("e2",)
    assert report.has_gaps is True
    with pytest.raises(ValueError, match="missing experiences"):
        reconstruct_trajectory(
            "t1", (e1, e3), expected_experience_ids=("e1", "e2", "e3")
        )


def test_duplicate_experience_is_explicitly_reported() -> None:
    e1, e2 = exp("e1", 1), exp("e2", 2)
    report = reconstruct_trajectory_diagnostics("t1", (e1, e2, e1))
    assert report.duplicate_experience_ids == ("e1",)
    with pytest.raises(ValueError, match="duplicate experiences"):
        reconstruct_trajectory("t1", (e1, e2, e1))


def test_reconstruction_does_not_mutate_experiences() -> None:
    e1, e2 = exp("e1", 1), exp("e2", 2)
    before = (e2, e1)
    reconstruct_trajectory("t1", before)
    assert before == (e2, e1)
