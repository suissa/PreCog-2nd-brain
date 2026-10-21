from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/checkpoint_evidence_bundle.sh"


def test_evidence_bundle_help_is_read_only() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "does not install, enable, start, stop, or modify" in result.stdout


def test_evidence_bundle_rejects_unknown_options() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--unsafe"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "Usage:" in result.stderr


def test_evidence_bundle_has_no_mutating_systemd_commands() -> None:
    content = SCRIPT.read_text()
    for command in (
        "systemctl --user enable",
        "systemctl --user disable",
        "systemctl --user start",
        "systemctl --user stop",
        "systemctl --user restart",
        "daemon-reload",
    ):
        assert command not in content


def test_evidence_bundle_redacts_common_secret_forms() -> None:
    content = SCRIPT.read_text()
    assert "[REDACTED]" in content
    assert "PASSWORD|SECRET|TOKEN|PRIVATE_KEY" in content
    assert "postgres(ql)?://" in content
