#!/usr/bin/env python3
r"""R31 source audit: restore stock Okidata 92/93 and add OkiGraph as type 10.

This is diagnostic-only. It fetches the historical 1987 Print Shop sources
through the existing source loader and prints the printer selector/table
contexts needed to split the current type-5 overload safely.
"""

from __future__ import annotations

import pathlib
import re

from patch_printshop_source import (
    binary_source_info,
    binary_source_text,
    file_sector_locations,
    load_image,
    patch_menus,
    patch_prcoms,
)


def show_hits(lines: list[str], pattern: str, radius: int = 8) -> None:
    rx = re.compile(pattern, re.I)
    hits = [i for i, line in enumerate(lines) if rx.search(line)]
    print(f"pattern {pattern!r}: {len(hits)} hit(s)")
    shown: set[tuple[int, int]] = set()
    for i in hits:
        lo = max(0, i - radius)
        hi = min(len(lines), i + radius + 1)
        key = (lo, hi)
        if key in shown:
            continue
        shown.add(key)
        print(f"-- around line {i + 1} --")
        for n in range(lo, hi):
            print(f"{n + 1:5d}: {lines[n]}")
        print("")


def show_labels_containing(lines: list[str], token: str) -> None:
    token = token.upper()
    print(f"labels/lines containing {token}:")
    for i, line in enumerate(lines):
        if token in line.upper():
            print(f"{i + 1:5d}: {line}")
    print("")


def main() -> int:
    d1 = load_image(None, 0)
    d2 = load_image(None, 1)
    pr = binary_source_text(d1, "PRCOMS.S")
    menus = binary_source_text(d2, "MENUS7.S")

    pl = pr.splitlines()
    ml = menus.splitlines()

    print("=== EXACT MENUS7 PRINTER BLOCK ===")
    for n in range(1, min(181, len(ml) + 1)):
        print(f"{n:5d}: {ml[n - 1]}")
    print("")

    print("=== PRCOMS SYMBOL / ZERO-PAGE MAP ===")
    for n in range(1, min(120, len(pl) + 1)):
        print(f"{n:5d}: {pl[n - 1]}")
    print("")

    print("=== EXACT PRCOMS CORE BLOCKS ===")
    for lo, hi in ((120, 245), (330, 455), (465, 510)):
        print(f"-- PRCOMS lines {lo}-{hi} --")
        for n in range(lo, min(hi + 1, len(pl) + 1)):
            print(f"{n:5d}: {pl[n - 1]}")
        print("")

    for pat in (r"\\bPRMAX\\b", r"\\bPRLIST\\b", r"\\bPRPARAMS\\b"):
        show_hits(ml, pat, radius=5)

    print("=== DOS ALLOCATION BUDGET ===")
    for img, name, patcher in (
        (d1, "PRCOMS.S", patch_prcoms),
        (d2, "MENUS7.S", patch_menus),
    ):
        info = binary_source_info(img, name)
        locs = file_sector_locations(img, info["entry"])
        capacity = len(locs) * 256
        original_payload = len(info["payload"])
        patched_text = patcher(info["text"])
        patched_payload = len(
            patched_text.replace("\\n", "\\r").encode("ascii")
        )
        print(
            f"{name}: sectors={len(locs)} capacity={capacity} "
            f"original_payload={original_payload} "
            f"current_patched_payload={patched_payload} "
            f"remaining_after_header="
            f"{capacity - 4 - patched_payload}"
        )
    print("")

    print("=== PRCOMS TYPE DISPATCH / TABLE AUDIT ===")
    for pat in (
        r"\bPRTYPE\b",
        r"\bPITYPE\b",
        r"\bGC5\b",
        r"\bSGC5\b",
        r"\bSETLF5\b",
        r"CMP\s+#0?5\b",
        r"CPX\s+#0?5\b",
        r"CPY\s+#0?5\b",
        r"DFB|HEX|DA\b",
    ):
        show_hits(pl, pat, radius=9)

    print("=== MENUS7 PRINTER SELECTOR AUDIT ===")
    for pat in (
        r"OKIDATA",
        r"EPSON|IMAGEWRITER|DMP|C\. ITOH|PANASONIC|NEC|PROWRITER",
        r"\bGSELECT\b",
        r"\bPRTYPE\b",
        r"PRINTER",
        r"DFB|HEX|DA\b",
        r"CMP\s+#0?9\b",
        r"CMP\s+#10\b",
        r"LDX\s+#0?9\b",
        r"LDX\s+#10\b",
    ):
        show_hits(ml, pat, radius=10)

    print("=== MENU SOURCE SIZE / TAIL ===")
    print(f"MENUS7.S decoded chars: {len(menus)}")
    for n in range(max(0, len(ml) - 90), len(ml)):
        print(f"{n + 1:5d}: {ml[n]}")

    print("")
    print("=== CRLF CALL-SITE TUPLE AUDIT ===")
    for disk_index, img in enumerate((d1, d2), start=1):
        for entry in catalog(img):
            name = entry["name"]
            if not name.endswith(".S"):
                continue
            try:
                src = binary_source_text(img, name)
            except Exception:
                continue
            sl = src.splitlines()
            for i, line in enumerate(sl):
                if "JSR CRLF" not in line.upper():
                    continue
                lo = max(0, i - 5)
                context = " | ".join(
                    " ".join(x.strip().split())
                    for x in sl[lo:i + 1]
                )
                print(
                    f"disk{disk_index} {name} line {i + 1}: {context}"
                )
    print("")

    print("=== R31 QUESTIONS TO ANSWER ===")
    print("1. Is printer type 10 unused by all PRCOMS dispatch tables?")
    print("2. How is the printer-menu item count bounded?")
    print("3. Are printer names inline fixed-width strings or pointer-driven?")
    print("4. Can type 10 alias type 5's generic graphics transform while")
    print("   selecting separate CR/LF / SENDGC / output state?")
    print("5. What exact original type-5 bytes must be restored?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
