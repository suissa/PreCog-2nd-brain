"""Validate Intent Trajectory STEP-03/04 traceability deterministically.

The gate is intentionally provider/database independent. It verifies that every
canonical branch has a named scenario test, a mapped implementation symbol,
and an explicit invariant assertion marker.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "tests" / "traceability.json"
TESTS = ROOT / "tests" / "test_scenarios.py"


def main() -> int:
    matrix = json.loads(MATRIX.read_text())
    tree = ast.parse(TESTS.read_text())
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    implementations = {
        node.name
        for path in (ROOT / "src" / "intent_trajectory").glob("*.py")
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    branches = {entry["branch"] for entry in matrix}
    expected = {
        "VALID_PROGRESS", "VALID_NO_PROGRESS", "VALID_RECOVERY",
        "VALID_TERMINAL", "INVALID_INPUT", "INVALID_STATE",
        "INVALID_TRANSITION", "INVALID_EVIDENCE", "INVALID_CONSTRAINT",
        "INVALID_DESTINATION", "INVALID_TERMINATION",
    }
    errors: list[str] = []
    if branches != expected:
        errors.append(f"branch coverage mismatch: {sorted(expected - branches)} missing / {sorted(branches - expected)} unexpected")
    if len(matrix) != len(expected):
        errors.append(f"expected {len(expected)} traceability entries, found {len(matrix)}")

    for entry in matrix:
        test_name = entry["test"]
        symbol = entry["implementation_symbol"]
        invariant = entry["invariant"]
        node = functions.get(test_name)
        if node is None:
            errors.append(f"{entry['id']}: missing test {test_name}")
        if symbol not in implementations:
            errors.append(f"{entry['id']}: missing implementation symbol {symbol}")
        if not invariant.startswith("I"):
            errors.append(f"{entry['id']}: invalid invariant id {invariant}")
        if node is not None:
            source = ast.get_source_segment(TESTS.read_text(), node) or ""
            if f"invariant: {invariant}" not in source:
                errors.append(f"{entry['id']}: invariant {invariant} is not explicitly asserted/marked in {test_name}")

    report = {
        "scenario_count": len(matrix),
        "branch_count": len(branches),
        "implementation_symbols": sorted({e["implementation_symbol"] for e in matrix}),
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
