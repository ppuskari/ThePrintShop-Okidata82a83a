#!/usr/bin/env python3
"""Validate control and OkiGraph overlay builds."""

from __future__ import annotations

import argparse
import hashlib
import pathlib

EXPECTED = {
    "PRCOMS.ORIG": (1962, "6fb3928799f085967822362a3e7ba0b88dadd21e7e33372951e5734578c4629a"),
    "PRCOMS.OKI":  (1962, "1ade989cced56159d84d6bf1d37518726acfc9d65f8623ccc891d719452252cc"),
    "MENUS7.ORIG": (3014, "86d7fa76bfd693d461aa9085e3612253837e7f5f02a6027581beef3284c5355f"),
    "MENUS7.OKI":  (3014, "dcc17130eeb49dc829627dbd30e2594168d3c907b070a049850dc607742c6c32"),
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
        if len(data) != size:
            raise RuntimeError(f"{name}: expected {size} bytes, got {len(data)}")
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"{name}: expected {expected_hash}, got {actual_hash}"
            )
        print(f"{name}: PASS len={len(data)} sha256={actual_hash}")

    print("PASS: original controls and OkiGraph overlays are reproducible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
