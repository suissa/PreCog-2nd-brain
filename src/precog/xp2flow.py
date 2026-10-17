"""Deterministic structural validator for declarative XP.2Flow graphs.

This module validates graph structure and declared read/write effects. It does
not execute steps, call models, or mutate PreCog's canonical experience store.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Iterable


class FlowValidationError(ValueError):
    """Raised when an XP.2Flow definition violates its declared contract."""


@dataclass(frozen=True, slots=True)
class FlowStep:
    step_id: str
    kind: str
    depends_on: tuple[str, ...] = ()
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.step_id.strip():
            raise ValueError("step_id must be non-empty")
        if not self.kind.strip():
            raise ValueError("step kind must be non-empty")
        for label, values in (
            ("depends_on", self.depends_on),
            ("reads", self.reads),
            ("writes", self.writes),
        ):
            if any(not value.strip() for value in values):
                raise ValueError(f"{label} values must be non-empty")
            if len(set(values)) != len(values):
                raise ValueError(f"{label} values must be unique")


@dataclass(frozen=True, slots=True)
class XP2Flow:
    flow_id: str
    version: int
    steps: tuple[FlowStep, ...]

    def __post_init__(self) -> None:
        if not self.flow_id.strip():
            raise ValueError("flow_id must be non-empty")
        if self.version < 1:
            raise ValueError("flow version must be >= 1")


def _reachable_ancestors(
    ordered_ids: Iterable[str],
    dependencies: dict[str, tuple[str, ...]],
) -> dict[str, set[str]]:
    ancestors: dict[str, set[str]] = {}
    for step_id in ordered_ids:
        current: set[str] = set()
        for dependency in dependencies[step_id]:
            current.add(dependency)
            current.update(ancestors[dependency])
        ancestors[step_id] = current
    return ancestors


def validate_flow(
    flow: XP2Flow,
    *,
    registered_kinds: frozenset[str] | None = None,
) -> tuple[str, ...]:
    """Validate a flow and return a deterministic topological execution order.

    Steps that access a shared resource with conflicting read/write effects
    must be ordered through a dependency path. Independent steps may be
    reordered safely under the declared effect model.
    """
    if not flow.steps:
        raise FlowValidationError("flow must contain at least one step")

    by_id: dict[str, FlowStep] = {}
    for step in flow.steps:
        if step.step_id in by_id:
            raise FlowValidationError(f"duplicate step_id: {step.step_id}")
        by_id[step.step_id] = step
        if registered_kinds is not None and step.kind not in registered_kinds:
            raise FlowValidationError(f"unregistered step kind: {step.kind}")

    dependencies: dict[str, tuple[str, ...]] = {}
    successors: dict[str, list[str]] = {step_id: [] for step_id in by_id}
    indegree: dict[str, int] = {}
    for step_id, step in by_id.items():
        if step_id in step.depends_on:
            raise FlowValidationError(f"step cannot depend on itself: {step_id}")
        missing = sorted(set(step.depends_on) - by_id.keys())
        if missing:
            raise FlowValidationError(
                f"step {step_id} has unresolved dependencies: {', '.join(missing)}"
            )
        dependencies[step_id] = step.depends_on
        indegree[step_id] = len(step.depends_on)
        for dependency in step.depends_on:
            successors[dependency].append(step_id)

    ready = [step_id for step_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        step_id = heapq.heappop(ready)
        order.append(step_id)
        for successor in sorted(successors[step_id]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heapq.heappush(ready, successor)

    if len(order) != len(by_id):
        raise FlowValidationError("flow dependencies contain a cycle")

    ancestors = _reachable_ancestors(order, dependencies)
    ids = sorted(by_id)
    for index, left_id in enumerate(ids):
        left = by_id[left_id]
        left_writes = set(left.writes)
        for right_id in ids[index + 1:]:
            right = by_id[right_id]
            conflicts = (
                left_writes.intersection((*right.reads, *right.writes))
                or set(right.writes).intersection(left.reads)
            )
            if conflicts and (
                right_id not in ancestors[left_id]
                and left_id not in ancestors[right_id]
            ):
                resources = ", ".join(sorted(conflicts))
                raise FlowValidationError(
                    f"unordered steps {left_id} and {right_id} conflict on: {resources}"
                )

    return tuple(order)
