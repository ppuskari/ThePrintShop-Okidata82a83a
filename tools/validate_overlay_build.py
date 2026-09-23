#!/usr/bin/env python3
"""Validate control and OkiGraph overlay builds."""

from __future__ import annotations

import argparse
import hashlib
import pathlib

EXPECTED = {
    "PRCOMS.ORIG": (1962, "6fb3928799f085967822362a3e7ba0b88dadd21e7e33372951e5734578c4629a"),
    "PRCOMS.OKI":  (2043, "f0763857572ee113b2806fd0262d2f38b83d9f58571fa721a83867aad00d46a5"),
    "MENUS7.ORIG": (3014, "86d7fa76bfd693d461aa9085e3612253837e7f5f02a6027581beef3284c5355f"),
    "MENUS7.OKI":  (3018, "1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485"),
    "GCDRAW.ORIG": (2737, "cfa548eb4f950156c14639372f2681edbaa810e86f0945d73c24e0304e436353"),
    "GCDRAW.OKI":  (2810, "4bd76c9d9fbe1a32870b00edc3ca54061037dc6cd4491eb8202b5e7f26c9db4a"),
    "BDRAW.ORIG":  (1012, "787a97a6b6441724da019edf6ec586df3cf56acc61047db0b402553ac03699e4"),
    "BDRAW.OKI":   (None, None),
}


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_two_byte_runtime_delta(data: bytes, expected_hash: str) -> list[tuple[int, bytes]]:
    """Find two-byte deletions that reproduce a known historical runtime hash."""
    hits = []
    for offset in range(len(data) - 1):
        candidate = data[:offset] + data[offset + 2:]
        if hashlib.sha256(candidate).hexdigest() == expected_hash:
            hits.append((offset, data[offset:offset + 2]))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-dir", type=pathlib.Path, required=True)
    args = ap.parse_args()

    for name, (size, expected_hash) in EXPECTED.items():
        path = args.build_dir / name
        data = path.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        if size is not None and len(data) != size:
            if name == "BDRAW.ORIG" and len(data) == size + 2:
                hits = find_two_byte_runtime_delta(data, expected_hash)
                if len(hits) == 1:
                    off, removed = hits[0]
                    raise RuntimeError(
                        "BDRAW.ORIG historical source/runtime delta identified: "
                        f"assembled source is 2 bytes longer; deleting offset "
                        f"+0x{off:04X} bytes {removed.hex(' ')} reproduces the "
                        "known runtime DRAW4 hash. R29 must reconcile this "
                        "source/runtime difference before installing patched DRAW4."
                    )
                raise RuntimeError(
                    "BDRAW.ORIG is 2 bytes longer than runtime DRAW4, but "
                    f"two-byte hash reconciliation produced {len(hits)} matches"
                )
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
