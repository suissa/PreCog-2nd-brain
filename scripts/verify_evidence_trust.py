#!/usr/bin/env python3
"""Verify an evidence bundle against an authenticated trusted-key registry."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from precog.evidence_trust import verify_with_trust_store
from precog.evidence_trust_signature import verify_signed_trust_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--trust-store", required=True, type=Path)
    parser.add_argument("--root-public-key", required=True, type=Path,
                        help="out-of-band Ed25519 public key authenticating the trust registry")
    parser.add_argument("--key-id", help="require this exact trusted signer identity")
    args = parser.parse_args()
    registry_valid, registry_errors = verify_signed_trust_registry(
        args.trust_store, root_public_key_path=args.root_public_key
    )
    if not registry_valid:
        for error in registry_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("Trust registry: UNAUTHENTIC", file=sys.stderr)
        return 2
    valid, errors = verify_with_trust_store(
        args.bundle, trust_store_path=args.trust_store, expected_key_id=args.key_id
    )
    if valid:
        print("Evidence attestation: TRUSTED")
        return 0
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print("Evidence attestation: UNTRUSTED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
