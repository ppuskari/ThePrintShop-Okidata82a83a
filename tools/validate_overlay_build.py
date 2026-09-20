#!/usr/bin/env python3
"""Validate control and OkiGraph overlay builds."""

from __future__ import annotations

import argparse
import hashlib
import pathlib

EXPECTED = {
    "PRCOMS.ORIG": (1962, "6fb3928799f085967822362a3e7ba0b88dadd21e7e33372951e5734578c4629a"),
    "PRCOMS.OKI":  (2042, "d1cd460b9d8a6660395ed868e72c830437c3fe8e4a4a96ed63977e394ec07c90"),
    "MENUS7.ORIG": (3014, "86d7fa76bfd693d461aa9085e3612253837e7f5f02a6027581beef3284c5355f"),
    "MENUS7.OKI":  (3022, "6c35e2f9b1771c35a41f5686e1079d32f08d70bd75470f7f565c96c5fddb8bf8"),
}


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-dir", type=pathlib.Path, required=True)
    args = ap.parse_args()

    for name, (size, expected_hash) in EXPECTED.items():
        path = args.build_dir / name
        data = path.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        if size is not None and len(data) != size:
            raise RuntimeError(f"{name}: expected {size} bytes, got {len(data)}")
        if expected_hash is not None and actual_hash != expected_hash:
            raise RuntimeError(
                f"{name}: expected {expected_hash}, got {actual_hash}"
            )
        status = "DISCOVERY" if expected_hash is None else "PASS"
        print(f"{name}: {status} len={len(data)} sha256={actual_hash}")

    print("PASS: original controls and OkiGraph overlays are reproducible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
