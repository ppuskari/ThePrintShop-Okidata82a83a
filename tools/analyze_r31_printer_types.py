#!/usr/bin/env python3
r"""R31 source audit: restore stock Okidata 92/93 and add OkiGraph as type 10.

This is diagnostic-only. It fetches the historical 1987 Print Shop sources
through the existing source loader and prints the printer selector/table
contexts needed to split the current type-5 overload safely.
"""

from __future__ import annotations

import pathlib
import re

from inspect_printshop_source import catalog, fetch, file_sectors
from build_runtime_disk import (
    _referenced_sectors,
    _ts_list_sectors,
    _vtoc_sector_is_free,
)

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
    d3 = load_image(None, 2)
    pr = binary_source_text(d1, "PRCOMS.S")
    menus = binary_source_text(d2, "MENUS7.S")

    pl = pr.splitlines()
    ml = menus.splitlines()

    runtime = fetch(
        "https://mirrors.apple2.org.za/ftp.apple.asimov.net/"
        "images/productivity/graphics/printshop/ColorPrintShop.DSK"
    )
    runtime_names = [entry["name"] for entry in catalog(runtime)]
    print("=== RUNTIME DRAW FILE CATALOG ===")
    for name in runtime_names:
        if name.upper().startswith("DRAW"):
            print(name)
    for candidate in ("DRAW6", "DRAW7", "DRAW8"):
        state = "USED" if candidate in {n.upper() for n in runtime_names} else "FREE"
        print(f"{candidate}: {state}")
    print("")

    print("=== RUNTIME DISK SPACE AUDIT ===")
    referenced = _referenced_sectors(runtime)
    orphan_used = []
    vtoc_free = []
    for trk in range(3, 35):
        if trk == 17:
            continue
        for sec in range(16):
            free = _vtoc_sector_is_free(runtime, trk, sec)
            if free:
                vtoc_free.append((trk, sec))
            elif (trk, sec) not in referenced:
                orphan_used.append((trk, sec))
    print(f"VTOC-free non-system sectors: {len(vtoc_free)}")
    print(f"marked-used but unreferenced sectors: {len(orphan_used)}")
    if orphan_used:
        print(
            "orphan T/S: "
            + " ".join(f"T{t:02d}/S{s:02d}" for t, s in orphan_used)
        )
        print("orphan sector content:")
        by_digest = {}
        for trk, sec in orphan_used:
            start = (trk * 16 + sec) * 256
            data = runtime[start:start + 256]
            digest = __import__("hashlib").sha256(data).hexdigest()
            key = (
                digest,
                sum(1 for b in data if b != 0),
                sum(1 for b in data if b != 0xFF),
            )
            by_digest.setdefault(key, []).append((trk, sec, data))
        for (digest, nonzero, nonff), members in by_digest.items():
            sample = members[0][2]
            printable = "".join(
                chr(b) if 32 <= (b & 0x7F) < 127 else "."
                for b in sample[:64]
            )
            coords = " ".join(
                f"T{t:02d}/S{sec:02d}" for t, sec, _ in members
            )
            print(
                f"  {coords}: sha256={digest[:16]} "
                f"nonzero={nonzero}/256 nonff={nonff}/256 "
                f"preview={printable}"
            )

        live_sector_hashes = {}
        for entry in catalog(runtime):
            for index, (trk, sec) in enumerate(
                file_sector_locations(runtime, entry)
            ):
                start = (trk * 16 + sec) * 256
                data = runtime[start:start + 256]
                digest = __import__("hashlib").sha256(data).hexdigest()
                live_sector_hashes.setdefault(digest, []).append(
                    (entry["name"], index, trk, sec)
                )
        print("orphan exact matches to live file data sectors:")
        match_count = 0
        for trk, sec in orphan_used:
            start = (trk * 16 + sec) * 256
            data = runtime[start:start + 256]
            digest = __import__("hashlib").sha256(data).hexdigest()
            matches = live_sector_hashes.get(digest, [])
            if matches:
                match_count += 1
                formatted = " | ".join(
                    f"{name}[{index}]@T{lt:02d}/S{ls:02d}"
                    for name, index, lt, ls in matches
                )
                print(f"  T{trk:02d}/S{sec:02d} == {formatted}")
        print(f"exact duplicate orphan sectors: {match_count}/{len(orphan_used)}")

    binary_rows = []
    duplicate_groups = {}
    for entry in catalog(runtime):
        data_locs = file_sector_locations(runtime, entry)
        ts_locs = _ts_list_sectors(runtime, entry)
        raw = file_sectors(runtime, entry)
        if entry["type"] == 4 and len(raw) >= 4:
            logical = raw[2] | (raw[3] << 8)
            if 0 < logical <= len(raw) - 4:
                needed_data = (4 + logical + 255) // 256
                extra_data = len(data_locs) - needed_data
                logical_blob = raw[:4 + logical]
                digest = __import__("hashlib").sha256(logical_blob).hexdigest()
                binary_rows.append(
                    (
                        entry["name"], logical, len(data_locs),
                        len(ts_locs), extra_data, digest,
                    )
                )
                duplicate_groups.setdefault(digest, []).append(
                    (entry["name"], len(data_locs), len(ts_locs), logical)
                )
    reclaim_extra = sum(max(0, row[4]) for row in binary_rows)
    print(f"whole extra data sectors in binary files: {reclaim_extra}")
    for row in binary_rows:
        if row[4] > 0:
            print(
                f"  overallocated {row[0]}: payload={row[1]} "
                f"data={row[2]} ts={row[3]} extra_data={row[4]}"
            )
    print("duplicate logical binary groups:")
    dup_count = 0
    for digest, group in duplicate_groups.items():
        if len(group) < 2:
            continue
        dup_count += 1
        print(
            "  "
            + digest[:12]
            + " "
            + " | ".join(
                f"{name}(payload={logical},data={data},ts={ts})"
                for name, data, ts, logical in group
            )
        )
    if dup_count == 0:
        print("  none")
    print("")

    print("=== RUNTIME MENU FILE BUDGETS ===")
    runtime_entries = {e["name"].upper(): e for e in catalog(runtime)}
    for name in ("MENUS1", "MENUS3", "MENUS4", "DRAW1", "DRAW3", "DRAW4"):
        entry = runtime_entries[name]
        raw = file_sectors(runtime, entry)
        load = raw[0] | (raw[1] << 8)
        length = raw[2] | (raw[3] << 8)
        capacity = len(file_sector_locations(runtime, entry)) * 256
        print(
            f"{name}: load=0x{load:04X} payload={length} "
            f"capacity={capacity} spare={capacity - 4 - length}"
        )
    print("")

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
    print("=== GCDRAW SR MOVEMENT / DUMP AUDIT ===")
    gd = binary_source_text(d2, "GCDRAW.S").splitlines()
    for n in range(1320, min(1475, len(gd) + 1)):
        print(f"{n:5d}: {gd[n - 1]}")
    print("")

    print("=== BDRAW ICON SEND / RECLAIM AUDIT ===")
    bd = binary_source_text(d2, "BDRAW.S").splitlines()
    for n in range(448, min(535, len(bd) + 1)):
        print(f"{n:5d}: {bd[n - 1]}")
    print("")

    print("=== CRLF CALL-SITE TUPLE AUDIT ===")
    for disk_index, img in enumerate((d1, d2, d3), start=1):
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

    print("=== PRECISE DRAW FILENAME LITERALS ===")
    def is_draw_literal(line: str) -> bool:
        compact = " ".join(line.strip().upper().split())
        return any(
            f"ASC 'DRAW{n}" in compact
            for n in range(1, 5)
        )
    for disk_index, img in enumerate((d1, d2, d3), start=1):
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
                if not is_draw_literal(line):
                    continue
                print(
                    f"-- disk{disk_index} {name} literal at line {i + 1} --"
                )
                for n in range(max(0, i - 18), min(len(sl), i + 28)):
                    print(f"{n + 1:5d}: {sl[n]}")
                print("")
    print("")

    print("=== DRAW STRING / DYNAMIC LOADER AUDIT ===")
    for disk_index, img in enumerate((d1, d2, d3), start=1):
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
                u = " ".join(line.strip().upper().split())
                quoted_draw = (
                    ("ASC" in u or "HEX" in u)
                    and ("'DRAW" in u or '"DRAW' in u)
                )
                dynamic_draw = (
                    ("STA" in u or "INC" in u or "ADC" in u or "ORA" in u)
                    and ("DRAW" in u)
                )
                draw_bload = "BLOAD" in u and any(
                    "DRAW" in " ".join(x.strip().upper().split())
                    for x in sl[max(0, i - 12):i + 1]
                )
                if not (quoted_draw or dynamic_draw or draw_bload):
                    continue
                print(
                    f"-- disk{disk_index} {name} around line {i + 1} --"
                )
                for n in range(max(0, i - 15), min(len(sl), i + 22)):
                    print(f"{n + 1:5d}: {sl[n]}")
                print("")
    print("")

    print("=== DRAW OVERLAY LOADER AUDIT ===")
    overlay_terms = ("DRAW1", "DRAW2", "DRAW3", "DRAW4", "BLOAD", "DRAW")
    for disk_index, img in enumerate((d1, d2, d3), start=1):
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
                u = line.upper()
                if not any(term in u for term in overlay_terms):
                    continue
                if "DRAW" not in u and "BLOAD" not in u:
                    continue
                lo = max(0, i - 5)
                hi = min(len(sl), i + 8)
                print(
                    f"-- disk{disk_index} {name} around line {i + 1} --"
                )
                for n in range(lo, hi):
                    print(f"{n + 1:5d}: {sl[n]}")
                print("")
    print("")

    print("=== CONFIG+6 / $95F6 UNUSED-BYTE AUDIT ===")
    config_patterns = (
        "$95F6", "$95f6", "CONFIG+6", "PISLOT+6",
        "CONFIG + 6", "PISLOT + 6",
    )
    total_hits = 0
    for disk_index, img in enumerate((d1, d2, d3), start=1):
        for entry in catalog(img):
            name = entry["name"]
            if not name.endswith(".S"):
                continue
            try:
                src = binary_source_text(img, name)
            except Exception:
                continue
            for line_no, line in enumerate(src.splitlines(), start=1):
                if any(p in line for p in config_patterns):
                    print(
                        f"disk{disk_index} {name}:{line_no}: "
                        f"{line.strip()}"
                    )
                    total_hits += 1
    print(f"CONFIG+6 audit hits: {total_hits}")
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
