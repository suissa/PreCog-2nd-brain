import subprocess
import sys


def test_checkpoint_cli_exposes_local_incident_log_option() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/checkpoint_promotion_audit.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--incident-log" in result.stdout
    assert "PRECOG_AUDIT_INCIDENT_LOG" in result.stdout
