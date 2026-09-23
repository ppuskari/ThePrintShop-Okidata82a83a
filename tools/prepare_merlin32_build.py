#!/usr/bin/env python3
"""Prepare historical Print Shop sources for reproducible Merlin32 assembly."""

from __future__ import annotations

import argparse
import pathlib
import re

from patch_printshop_source import (
    binary_source_text,
    load_image,
    patch_bdraw,
    patch_gcdraw,
    patch_menus,
    patch_prcoms,
)


def normalize_bigmac(text: str) -> str:
    # Big Mac accepts punctuation character immediates such as #','.
    # Merlin32 wants these expressed numerically.
    return re.sub(
        r"#'([^'])'",
        lambda m: "#$%02X" % ord(m.group(1)),
        text,
    )


def add_sav(text: str, output_name: str) -> str:
    lines = normalize_bigmac(text).splitlines()
    idx = next(
        (
            i for i in range(len(lines) - 1, -1, -1)
            if lines[i].strip().upper() == "END"
        ),
        None,
    )
    if idx is None:
        raise RuntimeError("source has no final END directive")
    lines.insert(idx, f" SAV {output_name}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=pathlib.Path, required=True)
    args = ap.parse_args()

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    d1 = load_image(None, 0)
    d2 = load_image(None, 1)
    prcoms_orig = binary_source_text(d1, "PRCOMS.S")
    menus7_orig = binary_source_text(d2, "MENUS7.S")
    gcdraw_orig = binary_source_text(d2, "GCDRAW.S")
    bdraw_orig = binary_source_text(d2, "BDRAW.S")
    prcoms_oki = patch_prcoms(prcoms_orig)
    menus7_oki = patch_menus(menus7_orig)
    gcdraw_oki = patch_gcdraw(gcdraw_orig)
    bdraw_oki = patch_bdraw(bdraw_orig)

    # Temporary compact R29 source-layout discovery.  This prints only the
    # small banner control-flow neighborhoods needed to make a size-neutral
    # patch; the historical source itself is not stored in the repository.
    lines = bdraw_orig.splitlines()
    for marker in ("BSTR6", "CPY #40", "JMP BSTR6", "BICON2"):
        for i, line in enumerate(lines):
            if marker in line:
                lo = max(0, i - (35 if marker == "BICON2" else 5))
                hi = min(len(lines), i + 8)
                print(f"R29-BDRAW-CONTEXT {marker}:")
                for row in lines[lo:hi]:
                    print("  " + row)
                break
    for i, line in enumerate(lines):
        if "JMP " in line:
            print(f"R29-BDRAW-JMP {i + 1}:")
            for row in lines[max(0, i - 4):min(len(lines), i + 3)]:
                print("  " + row)

    products = {
        "PRCOMS.ORIG.BUILD.S": add_sav(prcoms_orig, "PRCOMS.ORIG"),
        "PRCOMS.OKI.BUILD.S": add_sav(prcoms_oki, "PRCOMS.OKI"),
        "MENUS7.ORIG.BUILD.S": add_sav(menus7_orig, "MENUS7.ORIG"),
        "MENUS7.OKI.BUILD.S": add_sav(menus7_oki, "MENUS7.OKI"),
        "GCDRAW.ORIG.BUILD.S": add_sav(gcdraw_orig, "GCDRAW.ORIG"),
        "GCDRAW.OKI.BUILD.S": add_sav(gcdraw_oki, "GCDRAW.OKI"),
        "BDRAW.ORIG.BUILD.S": add_sav(bdraw_orig, "BDRAW.ORIG"),
        "BDRAW.OKI.BUILD.S": add_sav(bdraw_oki, "BDRAW.OKI"),
    }

    for name, text in products.items():
        (out / name).write_text(text, encoding="ascii", newline="\n")
        print(out / name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
