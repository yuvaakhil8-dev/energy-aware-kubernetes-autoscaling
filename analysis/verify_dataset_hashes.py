#!/usr/bin/env python3
"""Verify that the two original datasets are byte-for-byte unchanged."""
from __future__ import annotations

import hashlib
import os
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(APP_DIR)
EXPECTED = {
    "experiment_results_v2.json": "6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E",
    "experiment_results.json": "C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451",
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> int:
    failed = 0
    for name, expected in EXPECTED.items():
        original = os.path.join(PROJECT_ROOT, name)
        copy = os.path.join(APP_DIR, "data", name)
        if os.path.exists(original):
            actual = sha256(original)
            status = "PASS" if actual == expected else "FAIL"
            print(f"{status} original {name} {actual}")
            if actual != expected:
                failed += 1
        else:
            print(f"NOTE original workspace copy not present: {original}")
        if not os.path.exists(copy):
            print(f"FAIL missing tracked copy {copy}")
            failed += 1
            continue
        actual = sha256(copy)
        status = "PASS" if actual == expected else "FAIL"
        print(f"{status} data/{name} {actual}")
        if actual != expected:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
