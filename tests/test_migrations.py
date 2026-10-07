from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INITIAL = (ROOT / "sql/001_initial.sql").read_text()
HARDENING = (ROOT / "sql/002_canonical_constraints.sql").read_text()
ROLLBACK = (ROOT / "sql/002_canonical_constraints_down.sql").read_text()


def test_phase0_migrations_have_canonical_entities() -> None:
    for entity in ("experience", "trajectory", "memory", "knowledge", "relation"):
        assert f"CREATE TABLE IF NOT EXISTS {entity}" in INITIAL
    assert "CREATE TABLE IF NOT EXISTS behavior" in HARDENING


def test_phase0_schema_versions_and_temporal_checks_are_explicit() -> None:
    assert "schema_version INTEGER NOT NULL DEFAULT 1" in INITIAL
    assert "schema_version_positive" in HARDENING
    assert "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from" in INITIAL


def test_phase0_derived_provenance_and_behavior_constraints_exist() -> None:
    assert "knowledge_provenance_required" in HARDENING
    assert "relation_provenance_required" in HARDENING
    assert "Behavior is downstream" not in HARDENING
    assert "behavior_id" in INITIAL
    assert "CREATE INDEX IF NOT EXISTS behavior_status_idx" in HARDENING


def test_phase0_rollback_reverses_hardening_without_deleting_experience() -> None:
    assert "DROP TABLE IF EXISTS behavior" in ROLLBACK
    assert "DROP TABLE experience" not in ROLLBACK
    assert "DROP TABLE trajectory" not in ROLLBACK
    assert "DROP TABLE memory" not in ROLLBACK
