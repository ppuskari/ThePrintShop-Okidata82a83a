#!/usr/bin/env python3
"""Validate control and OkiGraph overlay builds."""

from __future__ import annotations

import argparse
import hashlib
import pathlib

EXPECTED = {
    "PRCOMS.ORIG": (1962, "6fb3928799f085967822362a3e7ba0b88dadd21e7e33372951e5734578c4629a"),
    "PRCOMS.OKI":  (2043, "74ec82b69ed2ccce454a4db9e8c70eef46bb0dcbacba84227156025501967118"),
    "MENUS7.ORIG": (3014, "86d7fa76bfd693d461aa9085e3612253837e7f5f02a6027581beef3284c5355f"),
    "MENUS7.OKI":  (3018, "1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485"),
    "GCDRAW.ORIG": (2737, "cfa548eb4f950156c14639372f2681edbaa810e86f0945d73c24e0304e436353"),
    "GCDRAW.OKI":  (2811, "eb2548a7b4cd55dd0456da6ab9bc7ebbc600a0c33d37ec5787dd00ed3fc93645"),
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
