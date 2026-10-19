import os
import subprocess
import sys
from pathlib import Path


def test_checkpoint_cli_exposes_local_incident_log_option() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/checkpoint_promotion_audit.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--incident-log" in result.stdout
    assert "PRECOG_AUDIT_INCIDENT_LOG" in result.stdout


def test_checkpoint_cli_documents_freshness_environment_variable() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/checkpoint_promotion_audit.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--max-checkpoint-age-seconds" in result.stdout
    assert "PRECOG_MAX_CHECKPOINT_AGE_SECONDS" in result.stdout


def test_systemd_installer_mentions_both_timers_and_keeps_existing_config(tmp_path: Path) -> None:
    script = Path("scripts/install_checkpoint_systemd.sh").read_text(encoding="utf-8")
    assert "precog-checkpoint-create.timer" in script
    assert "precog-checkpoint-verify.timer" in script
    assert 'if [[ ! -e "$env_file" ]]' in script
    assert "chmod 600" in script
    assert "lingering" in script
