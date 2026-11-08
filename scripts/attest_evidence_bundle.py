#!/usr/bin/env python3
"""Sign or verify a PreCog operational evidence bundle."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from precog.evidence_attestation import sign_bundle, verify_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sign = sub.add_parser("sign", help="create a detached Ed25519 attestation (no overwrite)")
    sign.add_argument("bundle", type=Path)
    sign.add_argument("--private-key", required=True, type=Path)
    sign.add_argument("--key-id", required=True)
    verify = sub.add_parser("verify", help="verify signature and all evidence files")
    verify.add_argument("bundle", type=Path)
    verify.add_argument("--public-key", required=True, type=Path)
    verify.add_argument("--key-id", help="expected trusted key ID")
    args = parser.parse_args()

    try:
        if args.command == "sign":
            path = sign_bundle(args.bundle, private_key_path=args.private_key, key_id=args.key_id)
            print(f"Attestation created: {path}")
            return 0
        valid, errors = verify_bundle(args.bundle, public_key_path=args.public_key, expected_key_id=args.key_id)
        if valid:
            print("Evidence attestation: VALID")
            return 0
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("Evidence attestation: INVALID", file=sys.stderr)
        return 1
    except (OSError, ValueError, FileExistsError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
