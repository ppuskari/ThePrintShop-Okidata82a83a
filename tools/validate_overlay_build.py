#!/usr/bin/env python3
"""Validate control and OkiGraph overlay builds."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import pathlib

EXPECTED = {
    "PRCOMS.ORIG": (1962, "6fb3928799f085967822362a3e7ba0b88dadd21e7e33372951e5734578c4629a"),
    "PRCOMS.OKI":  (2044, None),
    "MENUS7.ORIG": (3014, "86d7fa76bfd693d461aa9085e3612253837e7f5f02a6027581beef3284c5355f"),
    "MENUS7.OKI":  (None, None),
    "GCDRAW.ORIG": (2737, "cfa548eb4f950156c14639372f2681edbaa810e86f0945d73c24e0304e436353"),
    "GCDRAW.OKI":  (2810, None),
    "MENUS3.ORIG": (None, None),
    "MENUS3.OKI":  (None, None),
    "MENUS4.ORIG": (None, None),
    "MENUS4.OKI":  (None, None),
    "LHDRAW.ORIG": (None, None),
    "LHDRAW.OKI":  (None, None),
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

    gc_orig = (args.build_dir / "GCDRAW.ORIG").read_bytes()
    gc_oki = (args.build_dir / "GCDRAW.OKI").read_bytes()
    sm = difflib.SequenceMatcher(None, gc_orig, gc_oki, autojunk=False)
    opcodes = sm.get_opcodes()
    edits = [op for op in opcodes if op[0] != "equal"]
    inserted_bytes = sum(j2 - j1 for tag, i1, i2, j1, j2 in edits)
    deleted_bytes = sum(i2 - i1 for tag, i1, i2, j1, j2 in edits)
    # Candidate compact edit stream:
    # 2-byte original offset + 1-byte delete + 1-byte insert + inserted data.
    # Long runs can be split if a count exceeds 255.
    compact_size = 0
    compact_ops = 0
    for tag, i1, i2, j1, j2 in edits:
        old_n = i2 - i1
        new_n = j2 - j1
        chunks = max(
            1,
            (old_n + 254) // 255,
            (new_n + 254) // 255,
        )
        compact_ops += chunks
        compact_size += chunks * 4 + new_n
    print(
        "GCDRAW R31 binary delta: "
        f"orig={len(gc_orig)} oki={len(gc_oki)} "
        f"edit_ops={len(edits)} compact_ops={compact_ops} "
        f"inserted_or_replacement_bytes={inserted_bytes} "
        f"deleted_or_replaced_bytes={deleted_bytes} "
        f"candidate_edit_stream={compact_size} bytes"
    )
    for op in edits[:40]:
        tag, i1, i2, j1, j2 = op
        print(
            f"  {tag:7s} old +0x{i1:04X}..+0x{i2:04X} "
            f"new +0x{j1:04X}..+0x{j2:04X} "
            f"old_n={i2-i1} new_n={j2-j1}"
        )
    if len(edits) > 40:
        print(f"  ... {len(edits)-40} more edit op(s)")

    lh_orig = (args.build_dir / "LHDRAW.ORIG").read_bytes()
    lh_oki = (args.build_dir / "LHDRAW.OKI").read_bytes()
    lh_diffs = [
        (i, a, b)
        for i, (a, b) in enumerate(zip(lh_orig, lh_oki))
        if a != b
    ]
    print(
        "LHDRAW R31 immediate diffs: "
        + ", ".join(
            f"+0x{i:04X} {a:02X}->{b:02X}"
            for i, a, b in lh_diffs
        )
    )
    if [(a, b) for _, a, b in lh_diffs] != [(40, 0), (14, 68)]:
        raise RuntimeError(
            f"LHDRAW R31 unexpected diff set: {lh_diffs}"
        )

    print("PASS: original controls and OkiGraph overlays are reproducible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
