#!/usr/bin/env python3
r"""R31 source audit: restore stock Okidata 92/93 and add OkiGraph as type 10.

This is diagnostic-only. It fetches the historical 1987 Print Shop sources
through the existing source loader and prints the printer selector/table
contexts needed to split the current type-5 overload safely.
"""

from __future__ import annotations

import pathlib
import re

from patch_printshop_source import binary_source_text, load_image


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
