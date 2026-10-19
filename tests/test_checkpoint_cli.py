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


def test_systemd_installer_requires_preflight_before_activation() -> None:
    script = Path("scripts/install_checkpoint_systemd.sh").read_text(encoding="utf-8")
    assert "precog-checkpoint-create.timer" in script
    assert "precog-checkpoint-verify.timer" in script
    assert 'if [[ ! -e "$env_file" ]]' in script
    assert "chmod 600" in script
    assert "lingering" in script
    assert "PRECOG_PYTHON=/usr/bin/python3" in script
    assert 'exec "${PRECOG_PYTHON:-python3}"' in script
    assert "checkpoint_preflight.py" in script
    assert 'if [[ "$created_config" -eq 1 ]]' in script
    assert "enable --now" in script
    syntax = subprocess.run(
        ["bash", "-n", "scripts/install_checkpoint_systemd.sh"],
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_checkpoint_preflight_fails_closed_on_missing_configuration() -> None:
    env = os.environ.copy()
    for name in (
        "PRECOG_REPO_DIR",
        "PRECOG_PYTHON",
        "DATABASE_URL",
        "PRECOG_CHECKPOINT_DIR",
        "PRECOG_PUBLIC_KEY_DIR",
        "PRECOG_PRIVATE_KEY_FILE",
        "PRECOG_PUBLIC_KEY_ID",
        "PRECOG_AUDIT_INCIDENT_LOG",
        "PRECOG_MAX_CHECKPOINT_AGE_SECONDS",
    ):
        env.pop(name, None)
    result = subprocess.run(
        [sys.executable, "scripts/checkpoint_preflight.py"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "missing configuration values" in result.stderr
    assert "DATABASE_URL" in result.stderr
    assert "PRECOG PREFLIGHT OK" not in result.stdout


def test_checkpoint_preflight_does_not_print_database_url_on_failure() -> None:
    env = os.environ.copy()
    env.update(
        {
            "PRECOG_REPO_DIR": str(Path.cwd()),
            "PRECOG_PYTHON": sys.executable,
            "DATABASE_URL": "postgresql://secret-user:secret-password@127.0.0.1:1/secret-db",
            "PRECOG_CHECKPOINT_DIR": str(Path("/tmp/precog-checkpoints-test")),
            "PRECOG_PUBLIC_KEY_DIR": str(Path("/tmp/precog-public-keys-test")),
            "PRECOG_PRIVATE_KEY_FILE": str(Path("/tmp/precog-private-test.pem")),
            "PRECOG_PUBLIC_KEY_ID": "key-1",
            "PRECOG_AUDIT_INCIDENT_LOG": str(Path("/tmp/precog-incidents-test/audit.jsonl")),
            "PRECOG_MAX_CHECKPOINT_AGE_SECONDS": "129600",
        }
    )
    result = subprocess.run(
        [sys.executable, "scripts/checkpoint_preflight.py"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "secret-password" not in result.stderr
    assert "secret-user" not in result.stderr
    assert "PRECOG PREFLIGHT FAILED" in result.stderr
