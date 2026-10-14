import io
import json
from pathlib import Path

import pytest

from precog.audit_incidents import LocalAuditIncidentSink


def test_local_incident_sink_appends_jsonl_and_writes_stderr(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "audit-incidents.jsonl"
    stderr = io.StringIO()
    sink = LocalAuditIncidentSink(path, stderr=stderr)

    sink.alert("checkpoint reconciliation failed: invalid signature")
    sink.alert("checkpoint creation failed: audit chain invalid")

    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(events) == 2
    assert all(event["kind"] == "audit_checkpoint_alert" for event in events)
    assert all(event["incident_id"] for event in events)
    assert events[0]["message"] == "checkpoint reconciliation failed: invalid signature"
    assert events[1]["message"] == "checkpoint creation failed: audit chain invalid"
    assert events[0]["incident_id"] != events[1]["incident_id"]
    assert "PRECOG AUDIT ALERT" in stderr.getvalue()


def test_local_incident_sink_rejects_empty_messages(tmp_path: Path) -> None:
    sink = LocalAuditIncidentSink(tmp_path / "audit.jsonl", stderr=io.StringIO())
    with pytest.raises(ValueError, match="must not be empty"):
        sink.alert("  ")
    assert not (tmp_path / "audit.jsonl").exists()


def test_local_incident_sink_sets_restrictive_file_permissions(tmp_path: Path) -> None:
    if not hasattr(Path, "chmod"):
        pytest.skip("filesystem permissions are unavailable")
    path = tmp_path / "audit.jsonl"
    LocalAuditIncidentSink(path, stderr=io.StringIO()).alert("local alert")
    assert path.stat().st_mode & 0o077 == 0
