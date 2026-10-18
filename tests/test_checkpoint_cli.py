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



def test_checkpoint_cli_exposes_checkpoint_freshness_option() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/checkpoint_promotion_audit.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--max-checkpoint-age-seconds" in result.stdout
    assert "PRECOG_MAX_CHECKPOINT_AGE_SECONDS" in result.stdout
