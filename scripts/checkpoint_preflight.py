#!/usr/bin/env python3
"""Validate local checkpoint scheduler configuration without creating a checkpoint."""
from __future__ import annotations

import argparse
import os
import re
import shlex
import stat
import sys
from pathlib import Path


def fail(message: str) -> int:
    print(f"PRECOG PREFLIGHT FAILED: {message}", file=sys.stderr)
    return 1


def read_environment_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE assignments without executing shell code."""
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            tokens = shlex.split(raw_line, comments=True, posix=True)
        except ValueError as error:
            raise ValueError(f"invalid environment-file syntax on line {line_number}") from error
        if not tokens:
            continue
        if len(tokens) != 1 or "=" not in tokens[0]:
            raise ValueError(f"expected one KEY=VALUE assignment on line {line_number}")
        name, value = tokens[0].split("=", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"invalid environment variable name on line {line_number}")
        values[name] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="read configuration without executing it")
    parser.add_argument(
        "--print-interpreter",
        action="store_true",
        help="print the configured interpreter path only (for installer bootstrap)",
    )
    args = parser.parse_args()

    if args.env_file is not None:
        try:
            configured = read_environment_file(args.env_file)
        except (OSError, ValueError) as error:
            return fail(f"cannot read configuration file ({type(error).__name__})")
        if args.print_interpreter:
            interpreter_value = configured.get("PRECOG_PYTHON", "")
            interpreter = Path(interpreter_value).expanduser()
            if not interpreter_value or not interpreter.is_absolute():
                return fail("PRECOG_PYTHON must be an absolute path")
            print(interpreter)
            return 0
        os.environ.update(configured)
    elif args.print_interpreter:
        return fail("--print-interpreter requires --env-file")

    required = (
        "PRECOG_REPO_DIR",
        "PRECOG_PYTHON",
        "DATABASE_URL",
        "PRECOG_CHECKPOINT_DIR",
        "PRECOG_PUBLIC_KEY_DIR",
        "PRECOG_PRIVATE_KEY_FILE",
        "PRECOG_PUBLIC_KEY_ID",
        "PRECOG_AUDIT_INCIDENT_LOG",
        "PRECOG_MAX_CHECKPOINT_AGE_SECONDS",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        return fail("missing configuration values: " + ", ".join(missing))

    repo = Path(os.environ["PRECOG_REPO_DIR"]).expanduser()
    if not repo.is_dir():
        return fail("PRECOG_REPO_DIR is not an existing directory")
    if not (repo / "scripts/checkpoint_promotion_audit.py").is_file():
        return fail("checkpoint audit CLI was not found in PRECOG_REPO_DIR")

    interpreter = Path(os.environ["PRECOG_PYTHON"]).expanduser()
    if not interpreter.is_absolute() or not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        return fail("PRECOG_PYTHON must be an absolute path to an executable file")

    try:
        max_age = float(os.environ["PRECOG_MAX_CHECKPOINT_AGE_SECONDS"])
        if max_age <= 0:
            return fail("PRECOG_MAX_CHECKPOINT_AGE_SECONDS must be greater than zero")
    except ValueError:
        return fail("PRECOG_MAX_CHECKPOINT_AGE_SECONDS must be numeric")

    key_id = os.environ["PRECOG_PUBLIC_KEY_ID"]
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", key_id):
        return fail("PRECOG_PUBLIC_KEY_ID contains unsupported characters")

    checkpoint_dir = Path(os.environ["PRECOG_CHECKPOINT_DIR"]).expanduser()
    incident_log = Path(os.environ["PRECOG_AUDIT_INCIDENT_LOG"]).expanduser()
    public_key_path = Path(os.environ["PRECOG_PUBLIC_KEY_DIR"]).expanduser() / f"{key_id}.pem"
    private_key_path = Path(os.environ["PRECOG_PRIVATE_KEY_FILE"]).expanduser()

    try:
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        incident_log.parent.mkdir(parents=True, exist_ok=True)
        for directory, label in ((checkpoint_dir, "checkpoint directory"), (incident_log.parent, "incident-log directory")):
            if not directory.is_dir() or not os.access(directory, os.W_OK | os.X_OK):
                return fail(f"{label} is not writable")
        if not public_key_path.is_file() or not os.access(public_key_path, os.R_OK):
            return fail(f"trusted public key is missing or unreadable: {public_key_path}")
        if not private_key_path.is_file() or not os.access(private_key_path, os.R_OK):
            return fail("private signing key is missing or unreadable")
        if os.name == "posix" and stat.S_IMODE(private_key_path.stat().st_mode) & 0o077:
            return fail("private signing key permissions are too broad; use chmod 600")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

        private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
        public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
        if not isinstance(private_key, Ed25519PrivateKey) or not isinstance(public_key, Ed25519PublicKey):
            return fail("checkpoint keys must be Ed25519 PEM keys")
        if private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ) != public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ):
            return fail("private signing key does not match the trusted public key")
    except (OSError, ValueError, TypeError) as error:
        return fail(f"filesystem or key validation failed ({type(error).__name__})")

    try:
        import psycopg
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    return fail("database connectivity probe returned an unexpected result")
    except ImportError:
        return fail("PostgreSQL adapter missing; install project extra with pip install '.[postgres]'")
    except Exception as error:
        # Never print connection exception text; it may contain the database URL.
        return fail(f"PostgreSQL connection probe failed ({type(error).__name__})")

    print("PRECOG PREFLIGHT OK: configuration, key pair, writable paths, and PostgreSQL connectivity validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
