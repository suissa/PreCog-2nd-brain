"""Validate Intent Trajectory STEP-03/04 traceability deterministically."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "tests" / "traceability.json"
TESTS = ROOT / "tests" / "test_scenarios.py"
EXPECTED = {
    "VALID_PROGRESS", "VALID_NO_PROGRESS", "VALID_RECOVERY", "VALID_TERMINAL",
    "INVALID_INPUT", "INVALID_STATE", "INVALID_TRANSITION", "INVALID_EVIDENCE",
    "INVALID_CONSTRAINT", "INVALID_DESTINATION", "INVALID_TERMINATION",
}


def main() -> int:
    test_source = TESTS.read_text()
    tree = ast.parse(test_source)
    functions = {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    implementations = set()
    for path in (ROOT / "src" / "intent_trajectory").glob("*.py"):
        module = ast.parse(path.read_text())
        implementations.update(
            node.name for node in ast.walk(module)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )

    matrix = json.loads(MATRIX.read_text())
    errors: list[str] = []
    branches = {entry["branch"] for entry in matrix}

    if branches != EXPECTED:
        errors.append(f"branch coverage mismatch: missing={sorted(EXPECTED - branches)} unexpected={sorted(branches - EXPECTED)}")
    if len(matrix) != len(EXPECTED):
        errors.append(f"expected {len(EXPECTED)} entries, found {len(matrix)}")

    for entry in matrix:
        scenario = entry["id"]
        test_name = entry["test"]
        symbol = entry["implementation_symbol"]
        invariant = entry["invariant"]
        if test_name not in functions:
            errors.append(f"{scenario}: missing test {test_name}")
        if symbol not in implementations:
            errors.append(f"{scenario}: missing implementation symbol {symbol}")
        if not invariant.startswith("I"):
            errors.append(f"{scenario}: invalid invariant {invariant}")
        if invariant not in test_source:
            errors.append(f"{scenario}: invariant {invariant} absent from scenario tests")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "scenario_count": len(matrix),
        "branch_count": len(branches),
        "errors": errors,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
