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
    assert "source " not in script
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


def test_checkpoint_preflight_reads_environment_file_without_executing_it(tmp_path: Path) -> None:
    marker = tmp_path / "should-not-exist"
    env_file = tmp_path / "checkpoint.env"
    env_file.write_text(
        f'PRECOG_PYTHON="{sys.executable}"\n'
        f'DATABASE_URL="postgresql://user:password@localhost/db"\n'
        f'PRECOG_REPO_DIR="{Path.cwd()}"\n'
        f'IGNORED="$(touch {marker})"\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/checkpoint_preflight.py",
            "--env-file",
            str(env_file),
            "--print-interpreter",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == sys.executable
    assert not marker.exists()


def test_checkpoint_preflight_rejects_shell_syntax_in_environment_file(tmp_path: Path) -> None:
    env_file = tmp_path / "checkpoint.env"
    env_file.write_text("PRECOG_PYTHON=/usr/bin/python3\n$(touch /tmp/precog-env-execution)\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/checkpoint_preflight.py", "--env-file", str(env_file), "--print-interpreter"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "invalid environment variable name" in result.stderr or "expected one KEY=VALUE assignment" in result.stderr


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



def _write_installer_fakes(tmp_path: Path, preflight_exit: int) -> tuple[Path, Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "systemctl-calls.log"
    systemctl = fake_bin / "systemctl"
    systemctl.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> {calls}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    systemctl.chmod(0o755)
    configured_python = tmp_path / "configured-python"
    configured_python.write_text(f"#!/bin/sh\nexit {preflight_exit}\n", encoding="utf-8")
    configured_python.chmod(0o755)
    return fake_bin, calls, configured_python


def test_installer_does_not_enable_timers_when_it_creates_template(tmp_path: Path) -> None:
    fake_bin, calls, _ = _write_installer_fakes(tmp_path, 0)
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{fake_bin}:{os.environ['PATH']}"})
    result = subprocess.run(
        ["bash", "scripts/install_checkpoint_systemd.sh", str(Path.cwd())],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "NOT enabled" in result.stdout
    assert calls.exists()
    calls_text = calls.read_text(encoding="utf-8")
    assert "daemon-reload" in calls_text
    assert "enable --now" not in calls_text
    config = home / ".config/precog/checkpoint.env"
    assert config.exists()
    assert config.stat().st_mode & 0o777 == 0o600


def test_installer_fails_closed_when_preflight_fails(tmp_path: Path) -> None:
    fake_bin, calls, configured_python = _write_installer_fakes(tmp_path, 1)
    home = tmp_path / "home"
    config_dir = home / ".config/precog"
    config_dir.mkdir(parents=True)
    env_file = config_dir / "checkpoint.env"
    env_file.write_text(
        f"PRECOG_REPO_DIR={Path.cwd()}\n"
        f"PRECOG_PYTHON={configured_python}\n"
        "DATABASE_URL=postgresql://user:password@localhost/db\n"
        "PRECOG_CHECKPOINT_DIR=/tmp/precog-test-checkpoints\n"
        "PRECOG_PUBLIC_KEY_DIR=/tmp/precog-test-public-keys\n"
        "PRECOG_PRIVATE_KEY_FILE=/tmp/precog-test-private.pem\n"
        "PRECOG_PUBLIC_KEY_ID=key-1\n"
        "PRECOG_AUDIT_INCIDENT_LOG=/tmp/precog-test-incidents/audit.jsonl\n"
        "PRECOG_MAX_CHECKPOINT_AGE_SECONDS=129600\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{fake_bin}:{os.environ['PATH']}"})
    result = subprocess.run(
        ["bash", "scripts/install_checkpoint_systemd.sh", str(Path.cwd())],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Preflight failed" in result.stderr
    calls_text = calls.read_text(encoding="utf-8")
    assert "daemon-reload" in calls_text
    assert "enable --now" not in calls_text


def test_installer_enables_timers_only_after_preflight_passes(tmp_path: Path) -> None:
    fake_bin, calls, configured_python = _write_installer_fakes(tmp_path, 0)
    home = tmp_path / "home"
    config_dir = home / ".config/precog"
    config_dir.mkdir(parents=True)
    env_file = config_dir / "checkpoint.env"
    env_file.write_text(
        f"PRECOG_REPO_DIR={Path.cwd()}\n"
        f"PRECOG_PYTHON={configured_python}\n"
        "DATABASE_URL=postgresql://user:password@localhost/db\n"
        "PRECOG_CHECKPOINT_DIR=/tmp/precog-test-checkpoints\n"
        "PRECOG_PUBLIC_KEY_DIR=/tmp/precog-test-public-keys\n"
        "PRECOG_PRIVATE_KEY_FILE=/tmp/precog-test-private.pem\n"
        "PRECOG_PUBLIC_KEY_ID=key-1\n"
        "PRECOG_AUDIT_INCIDENT_LOG=/tmp/precog-test-incidents/audit.jsonl\n"
        "PRECOG_MAX_CHECKPOINT_AGE_SECONDS=129600\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{fake_bin}:{os.environ['PATH']}"})
    result = subprocess.run(
        ["bash", "scripts/install_checkpoint_systemd.sh", str(Path.cwd())],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Preflight passed" in result.stdout
    calls_text = calls.read_text(encoding="utf-8")
    assert "daemon-reload" in calls_text
    assert "enable --now precog-checkpoint-create.timer precog-checkpoint-verify.timer" in calls_text
