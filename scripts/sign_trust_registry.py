#!/usr/bin/env python3
"""Sign a trust registry using its offline Ed25519 administrative key."""
from __future__ import annotations

import argparse
from pathlib import Path

from precog.evidence_trust_signature import sign_trust_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trust_store", type=Path)
    parser.add_argument("--private-key", required=True, type=Path)
    args = parser.parse_args()
    signature = sign_trust_registry(args.trust_store, private_key_path=args.private_key)
    print(f"Trust registry signature written: {signature}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
