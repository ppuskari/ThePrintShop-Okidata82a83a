#!/usr/bin/env python3
"""Report the original Print Shop v2 build structure from the source disks."""

from __future__ import annotations

import re
import urllib.parse

from inspect_printshop_source import BASE, NAMES, catalog, fetch, file_sectors


def decode(raw: bytes) -> str:
    if len(raw) >= 4:
        n = raw[2] | (raw[3] << 8)
        if 0 < n <= len(raw) - 4:
            raw = raw[4:4+n]
    raw = bytes(b & 0x7F for b in raw)
    return raw.decode("ascii", "replace").replace("\r", "\n").replace("\x00", "\n")


def get_file(img: bytes, name: str) -> str:
    for e in catalog(img):
        if e["name"].upper() == name.upper():
            return decode(file_sectors(img, e))
    raise KeyError(name)


def main() -> int:
    images = [fetch(BASE + urllib.parse.quote(n)) for n in NAMES]

    for d, img in enumerate(images, 1):
        print(f"=== SOURCE DISK {d} CATALOG ===")
        for e in catalog(img):
            print(
                f"{e['name']:<30} type=0x{e['type']:02X} "
                f"sectors={e['sectors']:3d} ts={e['ts_track']:02d}/{e['ts_sector']:02d}"
            )
        print()

        for name in ("HELLO", "CONFIG"):
            try:
                text = get_file(img, name)
            except KeyError:
                continue
            print(f"=== DISK {d} {name} ===")
            print(text[:20000])
            print()

    print("=== CRLF CALL SITES ACROSS SOURCE TREE ===")
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            text = decode(file_sectors(img, e))
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if re.search(r"\bJSR\s+CRLF\b", line, re.I):
                    lo = max(0, i - 10)
                    hi = min(len(lines), i + 8)
                    print(f"--- D{d} {e['name']} line {i + 1} ---")
                    for j in range(lo, hi):
                        print(f"{j + 1:5d}: {lines[j]}")
                    print()
    print()

    print("=== PRCOMS CONTROL-PATH REFERENCES ===")
    prcoms = get_file(images[0], "PRCOMS.S")
    for n, line in enumerate(prcoms.splitlines(), 1):
        if re.search(r"\b(SETLF|CRLF|SENDGC|GCOUT1|SGC5|GC5)\b", line, re.I):
            print(f"{n:5d}: {line}")
    print()

    print("=== ASSEMBLY DIRECTIVE SUMMARY ===")
    pat = re.compile(
        r"\b(ORG|OBJ|PUT|USE|INCLUDE|SAV|SAVE|BSAVE|BLOAD|EXEC|ASM|END|EQU)\b",
        re.I,
    )
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            text = decode(file_sectors(img, e))
            hits = []
            for n, line in enumerate(text.splitlines(), 1):
                if pat.search(line):
                    hits.append(f"{n:5d}: {line}")
            print(f"--- D{d} {e['name']} ---")
            print("\n".join(hits[:250]))
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
