from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_script_help_is_safe_and_documented() -> None:
    script = ROOT / "scripts/checkpoint_systemd_acceptance.sh"
    result = subprocess.run(
        ["bash", str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--run-jobs" in result.stdout
    assert "does not install, enable, disable, or modify units" in result.stdout


def test_acceptance_script_rejects_unknown_options() -> None:
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/checkpoint_systemd_acceptance.sh"), "--unsafe"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "Usage:" in result.stderr


def test_acceptance_script_requires_enabled_active_timers_before_running_jobs() -> None:
    content = (ROOT / "scripts/checkpoint_systemd_acceptance.sh").read_text()
    first_job = content.index('if [[ "$run_jobs" -eq 1 ]]')
    checks = content[:first_job]
    assert 'systemctl --user is-enabled --quiet "$timer"' in checks
    assert 'systemctl --user is-active --quiet "$timer"' in checks
    assert 'systemctl --user show "$timer" --property=LoadState --value' in checks
    assert 'systemctl --user start "$service"' not in checks


def test_acceptance_script_is_not_an_installer() -> None:
    content = (ROOT / "scripts/checkpoint_systemd_acceptance.sh").read_text()
    assert "systemctl --user enable" not in content
    assert "systemctl --user disable" not in content
    assert "daemon-reload" not in content
