#!/usr/bin/env python3
"""Verify an evidence bundle against an authenticated trusted-key registry."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from precog.evidence_trust import verify_with_trust_store
from precog.evidence_trust_signature import load_verified_trust_registry
from precog.trust_registry_anchor import verify_registry_anchor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--trust-store", required=True, type=Path)
    parser.add_argument("--root-public-key", required=True, type=Path,
                        help="out-of-band Ed25519 public key authenticating the trust registry")
    parser.add_argument("--key-id", help="require this exact trusted signer identity")
    parser.add_argument("--anchor-url", help="HTTPS URL of the independent monotonic anchor service")
    parser.add_argument("--anchor-public-key", type=Path,
                        help="out-of-band Ed25519 public key authenticating anchor responses")
    args = parser.parse_args()
    if bool(args.anchor_url) != bool(args.anchor_public_key):
        parser.error("--anchor-url and --anchor-public-key must be supplied together")

    registry, registry_errors = load_verified_trust_registry(
        args.trust_store, root_public_key_path=args.root_public_key
    )
    if registry is None:
        for error in registry_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("Trust registry: UNAUTHENTIC", file=sys.stderr)
        return 2

    if args.anchor_url is not None and args.anchor_public_key is not None:
        anchored, anchor_errors = verify_registry_anchor(
            registry,
            anchor_url=args.anchor_url,
            anchor_public_key_path=args.anchor_public_key,
        )
        if not anchored:
            for error in anchor_errors:
                print(f"ERROR: {error}", file=sys.stderr)
            print("Trust registry: ROLLBACK OR ANCHOR VERIFICATION FAILURE", file=sys.stderr)
            return 2

    valid, errors = verify_with_trust_store(
        args.bundle,
        trust_store_path=args.trust_store,
        expected_key_id=args.key_id,
        registry_data=registry,
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
