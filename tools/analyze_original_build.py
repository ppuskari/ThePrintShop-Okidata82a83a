#!/usr/bin/env python3
"""Report the original Print Shop v2 build structure from the source disks."""

from __future__ import annotations

import hashlib
import re
import urllib.parse

from inspect_printshop_source import BASE, NAMES, catalog, fetch, file_sectors
from build_runtime_disk import fetch_base as fetch_runtime_base


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
    runtime = fetch_runtime_base()
    print("=== COLOR PRINT SHOP RUNTIME GCDRAW ===")
    print("=== DRAW1 RUNTIME PAYLOAD HASH ===")
    for e in catalog(runtime):
        if e["name"].upper() == "DRAW1":
            raw = file_sectors(runtime, e)
            load = raw[0] | (raw[1] << 8)
            length = raw[2] | (raw[3] << 8)
            payload = raw[4:4 + length]
            print(
                f"DRAW1 load=0x{load:04X} len={len(payload)} "
                f"sha256={hashlib.sha256(payload).hexdigest()}"
            )
            break
    print()

    print("=== COLOR PRINT SHOP RUNTIME BINARY MAP ===")
    for e in catalog(runtime):
        raw = file_sectors(runtime, e)
        if e["type"] == 0x04 and len(raw) >= 4:
            load = raw[0] | (raw[1] << 8)
            length = raw[2] | (raw[3] << 8)
            print(
                f"{e['name']:<30} sectors={e['sectors']:<3} "
                f"load=0x{load:04X} len={length}"
            )
    print()

    print("=== GCDRAW SOURCE HEADER ===")
    gd = get_file(images[1], "GCDRAW.S").splitlines()
    for j in range(0, min(80, len(gd))):
        print(f"{j + 1:5d}: {gd[j]}")
    print()

    for e in catalog(runtime):
        if e["name"].upper() in ("PRCOMS", "MENUS7", "GCDRAW"):
            raw = file_sectors(runtime, e)
            head = raw[:16].hex()
            if len(raw) >= 4:
                load = raw[0] | (raw[1] << 8)
                length = raw[2] | (raw[3] << 8)
            else:
                load = length = -1
            print(
                f"{e['name']}: type=0x{e['type']:02X} sectors={e['sectors']} "
                f"raw={len(raw)} load=0x{load:04X} header_len={length} head={head}"
            )
    print()


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

    print("=== PRCOMS SETLF5 SOURCE ===")
    pr = get_file(images[0], "PRCOMS.S")
    prlines = pr.splitlines()
    for i, line in enumerate(prlines):
        if line.startswith("SETLF5"):
            for j in range(max(0, i - 2), min(len(prlines), i + 12)):
                print(f"{j + 1:5d}: {prlines[j]!r}")
            break
    print()

    print("=== PRCOMS ZERO-PAGE DEFINITIONS ===")
    prcoms_head = get_file(images[0], "PRCOMS.S")
    for n, line in enumerate(prcoms_head.splitlines()[:45], 1):
        print(f"{n:5d}: {line}")
    print()

    print("=== MENUS7 ENTRY REGION ===")
    menus7 = get_file(images[1], "MENUS7.S")
    for n, line in enumerate(menus7.splitlines()[:190], 1):
        print(f"{n:5d}: {line}")
    print()

    print("=== PRTYPE WRITE SITES ===")
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            txt = decode(file_sectors(img, e))
            lines = txt.splitlines()
            for i, line in enumerate(lines):
                if re.search(r"\b(STA|STX|STY)\s+PRTYPE\b", line, re.I):
                    lo = max(0, i - 10)
                    hi = min(len(lines), i + 12)
                    print(f"--- D{d} {e['name']} line {i + 1} ---")
                    for j in range(lo, hi):
                        print(f"{j + 1:5d}: {lines[j]}")
                    print()
    print()

    print("=== ZERO-PAGE B9/BC ALIASES ===")
    for addr in ("B9", "BC"):
        print(f"--- ${addr} ---")
        pat = re.compile(rf"\bEQU\s+\$?{addr}\b", re.I)
        for d, img in enumerate(images, 1):
            for e in catalog(img):
                if not e["name"].upper().endswith(".S"):
                    continue
                txt = decode(file_sectors(img, e))
                for n, line in enumerate(txt.splitlines(), 1):
                    if pat.search(line):
                        print("D{} {}:{}: {}".format(d, e["name"], n, line))
        print()
    print()

    print("=== SCRATCH SYMBOL REFERENCES ===")
    for symbol in ("FIX80", "GCINDEX", "GCOLD", "QL", "QH"):
        print(f"--- {symbol} ---")
        for d, img in enumerate(images, 1):
            for e in catalog(img):
                if not e["name"].upper().endswith(".S"):
                    continue
                txt = decode(file_sectors(img, e))
                for n, line in enumerate(txt.splitlines(), 1):
                    if re.search(rf"\b{symbol}\b", line, re.I):
                        print(f"D{d} {e['name']}:{n}: {line}")
        print()
    print()

    print("=== TARGET PRINT LOOPS ===")
    for disk_index, name, lo, hi in (
        (1, "GCDRAW.S", 1370, 1505),
        (2, "SMMENU2.S", 215, 310),
        (2, "LHDRAW.S", 665, 755),
    ):
        text = get_file(images[disk_index], name)
        lines = text.splitlines()
        print(f"--- D{disk_index + 1} {name} {lo}-{hi} ---")
        for j in range(lo - 1, min(hi, len(lines))):
            print(f"{j + 1:5d}: {lines[j]}")
        print()
    print()

    print("=== GCDRAW BLANK/TRIM AND COUNT TABLES ===")
    text = get_file(images[1], "GCDRAW.S")
    lines = text.splitlines()
    pats = (
        r"^BLANKS\b", r"^BLANK", r"GCNUM", r"^SENDGB\b",
        r"^SR0[1234]\b", r"RHALF", r"BUFPTR", r"BLANKCK"
    )
    hit_indexes = []
    for i, line in enumerate(lines):
        if any(re.search(p, line, re.I) for p in pats):
            hit_indexes.append(i)
    shown = set()
    for i in hit_indexes:
        lo = max(0, i - 10)
        hi = min(len(lines), i + 18)
        key = (lo, hi)
        if any(lo >= a and hi <= b for a,b in shown):
            continue
        shown.add(key)
        print(f"--- GCDRAW.S around line {i + 1} ---")
        for j in range(lo, hi):
            print(f"{j + 1:5d}: {lines[j]}")
        print()
    print()

    print("=== GCDRAW CRLF CONTEXTS ===")
    text = get_file(images[1], "GCDRAW.S")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.search(r"\b(JSR|JMP)\s+CRLF\b", line, re.I):
            lo = max(0, i - 14)
            hi = min(len(lines), i + 14)
            print(f"--- GCDRAW.S line {i + 1} ---")
            for j in range(lo, hi):
                print(f"{j + 1:5d}: {lines[j]}")
            print()
    print()

    print("=== SENDGC CALL SITES ACROSS SOURCE TREE ===")
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            text = decode(file_sectors(img, e))
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if re.search(r"\bJSR\s+SENDGC\b", line, re.I):
                    lo = max(0, i - 14)
                    hi = min(len(lines), i + 24)
                    print(f"--- D{d} {e['name']} line {i + 1} ---")
                    for j in range(lo, hi):
                        print(f"{j + 1:5d}: {lines[j]}")
                    print()
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

    print("=== GCDRAW DUMP RANGE 1335-1510 ===")
    gdump_range = get_file(images[1], "GCDRAW.S").splitlines()
    for j in range(1334, min(1510, len(gdump_range))):
        print(f"{j + 1:5d}: {gdump_range[j]}")
    print()

    print("=== GCDRAW DUMP OCCURRENCES ===")
    gdump_scan = get_file(images[1], "GCDRAW.S")
    for n, line in enumerate(gdump_scan.splitlines(), 1):
        if "DUMP" in line.upper():
            print(f"{n:5d}: {line}")
    print()

    print("=== GCDRAW DUMP ROUTINE ===")
    gdump = get_file(images[1], "GCDRAW.S").splitlines()
    for i, line in enumerate(gdump):
        if re.match(r"^DUMP\\b", line, re.I):
            lo = max(0, i - 25)
            hi = min(len(gdump), i + 180)
            for j in range(lo, hi):
                print(f"{j + 1:5d}: {gdump[j]}")
            break
    print()

    print("=== REVTBL DEFINITIONS / REFERENCES ===")
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            txt = decode(file_sectors(img, e))
            lines = txt.splitlines()
            for i, line in enumerate(lines):
                if "REVTBL" in line.upper():
                    lo = max(0, i - 6)
                    hi = min(len(lines), i + 20)
                    print("D{} {} line {}".format(d, e["name"], i + 1))
                    for j in range(lo, hi):
                        print(f"{j + 1:5d}: {lines[j]}")
                    print()
    print()

    print("=== GCDRAW SYMBOLS 1-110 ===")
    gcs = get_file(images[1], "GCDRAW.S").splitlines()
    for j in range(0, min(110, len(gcs))):
        print(f"{j + 1:5d}: {gcs[j]}")
    print()

    print("=== GCDRAW REVCHK / RASTER OUTPUT 1415-1610 ===")
    gcr = get_file(images[1], "GCDRAW.S").splitlines()
    for j in range(1414, min(1610, len(gcr))):
        print(f"{j + 1:5d}: {gcr[j]}")
    print()

    print("=== GCDRAW MAKEBUF 1510-1575 ===")
    gcmb = get_file(images[1], "GCDRAW.S").splitlines()
    for j in range(1509, min(1575, len(gcmb))):
        print(f"{j + 1:5d}: {gcmb[j]}")
    print()

    print("=== GCDRAW DUMP ROUTINE 1340-1515 ===")
    gcdump = get_file(images[1], "GCDRAW.S").splitlines()
    for j in range(1339, min(1515, len(gcdump))):
        print(f"{j + 1:5d}: {gcdump[j]}")
    print()

    print("=== GCDRAW STATUS/PRINT CONTROL 220-330 ===")
    gcstat = get_file(images[1], "GCDRAW.S").splitlines()
    for j in range(219, min(330, len(gcstat))):
        print(f"{j + 1:5d}: {gcstat[j]}")
    print()

    print("=== ALL STATUS-SYMBOL OCCURRENCES ===")
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            txt = decode(file_sectors(img, e))
            for n, line in enumerate(txt.splitlines(), 1):
                if any(sym in line.upper() for sym in ("THINKING", "PRINTING", "PAUSING")):
                    print("D{} {}:{}: {}".format(d, e["name"], n, line))
    print()

    print("=== PRCOMS STATUS ROUTINES 1045-1150 ===")
    prcoms_status = get_file(images[0], "PRCOMS.S").splitlines()
    for j in range(1044, min(1150, len(prcoms_status))):
        print(f"{j + 1:5d}: {prcoms_status[j]}")
    print()

    print("=== PRCOMS STATUS SYMBOL OCCURRENCES ===")
    prcoms_scan = get_file(images[0], "PRCOMS.S")
    for n, line in enumerate(prcoms_scan.splitlines(), 1):
        if any(sym in line.upper() for sym in ("THINKING", "PRINTING", "PAUSING")):
            print(f"{n:5d}: {line}")
    print()

    print("=== PRCOMS THINKING/PRINTING/PAUSING ===")
    prcoms = get_file(images[0], "PRCOMS.S")
    plines = prcoms.splitlines()
    for label in ("THINKING", "PRINTING", "PAUSING"):
        for i, line in enumerate(plines):
            if re.match(rf"^{label}\\b", line, re.I):
                lo = max(0, i - 10)
                hi = min(len(plines), i + 55)
                print(f"--- {label} at PRCOMS.S line {i + 1} ---")
                for j in range(lo, hi):
                    print(f"{j + 1:5d}: {plines[j]}")
                print()
                break
    print()

    print("=== THINKING/PRINTING CALL SITES ===")
    for symbol in ("THINKING", "PRINTING", "PAUSING"):
        print(f"--- {symbol} ---")
        for d, img in enumerate(images, 1):
            for e in catalog(img):
                if not e["name"].upper().endswith(".S"):
                    continue
                txt = decode(file_sectors(img, e))
                lines = txt.splitlines()
                for i, line in enumerate(lines):
                    if re.search(rf"\\b(JSR|JMP)\\s+{symbol}\\b", line, re.I):
                        lo = max(0, i - 8)
                        hi = min(len(lines), i + 12)
                        print("D{} {} line {}".format(d, e["name"], i + 1))
                        for j in range(lo, hi):
                            print(f"{j + 1:5d}: {lines[j]}")
                        print()
        print()
    print()
    print("=== PRCOMS TOP / COUT1 LAYOUT ===")
    prcoms = get_file(images[0], "PRCOMS.S")
    plines = prcoms.splitlines()
    for j in range(0, min(150, len(plines))):
        print(f"{j + 1:5d}: {plines[j]}")
    print()

    print("=== PRTYPE SYMBOL DEFINITIONS ===")
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            txt = decode(file_sectors(img, e))
            for n, line in enumerate(txt.splitlines(), 1):
                if re.search(r"^PRTYPE\\b", line, re.I):
                    print("D{} {}:{}: {}".format(d, e["name"], n, line))
    print()

    print("=== PRCOMS SENDGC/GCOUT1 TYPE-5 PATH ===")
    pr = get_file(images[0], "PRCOMS.S").splitlines()
    for label in ("SENDGC", "SGC5", "GCOUT1", "GC5", "SENDGB"):
        for i, line in enumerate(pr):
            if re.match(rf"^{label}\\b", line, re.I):
                lo = max(0, i - 8)
                hi = min(len(pr), i + 90)
                print(f"--- {label} at PRCOMS.S line {i + 1} ---")
                for j in range(lo, hi):
                    print(f"{j + 1:5d}: {pr[j]}")
                print()
                break
    print()

    print("=== DIRECT LF OUTPUT SITES ===")
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            txt = decode(file_sectors(img, e))
            lines = txt.splitlines()
            for i, line in enumerate(lines):
                if re.search(r"LDA\s+#\$?0A\b", line, re.I):
                    lo = max(0, i - 8)
                    hi = min(len(lines), i + 12)
                    block = "\n".join(lines[i:hi])
                    if re.search(r"\bCOUT1\b", block, re.I):
                        print(f"--- D{d} {e['name']} line {i + 1} ---")
                        for j in range(lo, hi):
                            print(f"{j + 1:5d}: {lines[j]}")
                        print()
    print()

    print("=== POSSIBLE DOUBLE-FEED / PRINT-START SITES ===")
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            txt = decode(file_sectors(img, e))
            lines = txt.splitlines()
            for i, line in enumerate(lines):
                up = line.upper()
                if (
                    re.search(r"LDY\s+#\$?0?2\b", up)
                    or "PRINT" in up
                    or "START" in up
                    or "TOP" in up
                ):
                    lo = max(0, i - 6)
                    hi = min(len(lines), i + 10)
                    block = "\n".join(lines[lo:hi])
                    if re.search(r"\bCRLF\b", block, re.I):
                        print(f"--- D{d} {e['name']} line {i + 1} ---")
                        for j in range(lo, hi):
                            print(f"{j + 1:5d}: {lines[j]}")
                        print()
    print()

    print("=== ALL IMMEDIATE CRLF CALLS ===")
    for d, img in enumerate(images, 1):
        for e in catalog(img):
            if not e["name"].upper().endswith(".S"):
                continue
            txt = decode(file_sectors(img, e))
            lines = txt.splitlines()
            for i, line in enumerate(lines):
                if re.search(r"\b(JSR|JMP)\s+CRLF\b", line, re.I):
                    lo = max(0, i - 8)
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
