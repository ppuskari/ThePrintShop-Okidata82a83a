#!/usr/bin/env python3
"""Focused R30 banner-text fit analysis for historical Print Shop BDRAW.S.

This deliberately does not patch anything. It extracts the archived 1987
BDRAW.S and reports the exact banner-text control-flow neighborhood needed to
decide whether the just-emitted raster row can be replayed cheaply for a true
3-source -> 4-printed-row densifier.

Run from repository root:

    py -3 tools\analyze_r30_banner.py

Optionally supply an already-downloaded source disk 2:

    py -3 tools\analyze_r30_banner.py --disk2 path\to\source2.dsk
"""

from __future__ import annotations

import argparse
import pathlib
import re

from patch_printshop_source import (
    binary_source_text,
    load_image,
)


LABEL_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)\b")


def label_of(line: str) -> str | None:
    if not line or line[0].isspace() or line.startswith("*"):
        return None
    m = LABEL_RE.match(line)
    return m.group(1).upper() if m else None


def print_lines(lines: list[str], lo: int, hi: int) -> None:
    lo = max(0, lo)
    hi = min(len(lines), hi)
    for i in range(lo, hi):
        print(f"{i + 1:5d}: {lines[i]}")


def find_label(lines: list[str], wanted: str) -> int:
    wanted = wanted.upper()
    hits = [i for i, line in enumerate(lines) if label_of(line) == wanted]
    if len(hits) != 1:
        raise RuntimeError(
            f"{wanted}: expected exactly one label, found {len(hits)}"
        )
    return hits[0]


def next_label(lines: list[str], start: int) -> int:
    for i in range(start + 1, len(lines)):
        if label_of(lines[i]) is not None:
            return i
    return len(lines)


def occurrences(lines: list[str], token: str) -> list[int]:
    token = token.upper()
    return [i for i, line in enumerate(lines) if token in line.upper()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--disk2",
        type=pathlib.Path,
        help="local 1987 source disk 2 instead of downloading",
    )
    args = ap.parse_args()

    disk2 = load_image(args.disk2, 1)
    source = binary_source_text(disk2, "BDRAW.S")
    lines = source.splitlines()

    print("R30 BDRAW.S banner-text fit analysis")
    print(f"source lines: {len(lines)}")
    print("")

    labels = {}
    for i, line in enumerate(lines):
        name = label_of(line)
        if name:
            labels.setdefault(name, []).append(i)

    banner_labels = sorted(
        (name, poss)
        for name, poss in labels.items()
        if name.startswith("BSTR") or name.startswith("BICON")
    )
    print("Banner labels:")
    for name, poss in banner_labels:
        print(
            f"  {name:<8} "
            + ", ".join(f"line {i + 1}" for i in poss)
        )
    print("")

    bstr2 = find_label(lines, "BSTR2")
    bstr6 = find_label(lines, "BSTR6")
    bicon2 = find_label(lines, "BICON2")

    # Show one contiguous window containing the text loop.
    print("=== BANNER TEXT CONTROL FLOW ===")
    print_lines(lines, max(0, bstr2 - 24), min(len(lines), bstr6 + 28))
    print("")

    print("=== BANNER ICON HOOK ===")
    print_lines(lines, max(0, bicon2 - 16), min(len(lines), bicon2 + 22))
    print("")

    print("=== SENDGC REFERENCES IN BDRAW.S ===")
    sendgc = occurrences(lines, "SENDGC")
    for idx in sendgc:
        print(f"-- SENDGC at line {idx + 1} --")
        print_lines(lines, idx - 8, idx + 9)
    print("")

    print("=== BITCNT REFERENCES ===")
    for idx in occurrences(lines, "BITCNT"):
        print_lines(lines, idx - 3, idx + 4)
        print("")
    print("=== XCUR REFERENCES ===")
    for idx in occurrences(lines, "XCUR"):
        print_lines(lines, idx - 3, idx + 4)
        print("")

    # The critical R30 question: is BSTR6 immediately downstream of a SENDGC?
    prior_send = [i for i in sendgc if i < bstr6]
    if prior_send:
        closest = prior_send[-1]
        print("=== REPLAY FIT CHECK ===")
        print(
            f"closest SENDGC before BSTR6: line {closest + 1}; "
            f"BSTR6: line {bstr6 + 1}; "
            f"distance: {bstr6 - closest} source lines"
        )
        print("Intervening source:")
        print_lines(lines, closest, bstr6 + 1)
        print("")

        between = "\n".join(lines[closest:bstr6 + 1]).upper()
        suspicious = []
        for token in (
            "INC ",
            "DEC ",
            "ASL ",
            "LSR ",
            "ROL ",
            "ROR ",
            "ADC ",
            "SBC ",
            "STA ",
            "STX ",
            "STY ",
        ):
            if token in between:
                suspicious.append(token.strip())
        if suspicious:
            print(
                "State-mutating instructions occur between SENDGC and BSTR6: "
                + ", ".join(sorted(set(suspicious)))
            )
            print(
                "A replay helper must preserve/restore their affected state "
                "or hook before those mutations."
            )
        else:
            print(
                "No obvious state mutation appears between SENDGC and BSTR6; "
                "direct row replay is a strong candidate."
            )
    else:
        print("No SENDGC found before BSTR6; direct replay is not established.")

    print("")
    print("=== R30 BYTE BUDGET BEFORE SOURCE RECLAIM ===")
    print(
        "BSTR6 fixed hook site: 7 bytes. R29 text enters only the final "
        "4 bytes of the shared helper ($7BF8-$7BFB)."
    )
    print(
        "Therefore text-only logic has 11 directly replaceable bytes while "
        "the known-good R29 icon entry at $7BF4 remains byte-for-byte frozen."
    )
    print(
        "Historical BSTR2 spacing setup is another 7-byte site "
        "(LDX #10 / LDY #0 / JSR CRLF). If the source flow proves that setup "
        "is obsolete under native-feed row replay, those bytes can host "
        "initialization/trampoline logic without shifting addresses."
    )
    print(
        "Practical option-2 fit threshold: direct replay should require only "
        "an existing row-output entry plus compact feed/selection logic. If "
        "the row must be rebuilt or font shift state restored, 18 fragmented "
        "bytes will not be enough and we must find another dead region."
    )
    print("")

    print("=== R29 FIXED RUNTIME CONTRACT ===")
    print("DRAW4 load          $7800")
    print("historical payload  1012 bytes ($7800-$7BF3)")
    print("R29 helper          $7BF4-$7BFB")
    print("R29 payload         1020 bytes, four sectors exactly")
    print("text hook offset    +$0085")
    print("icon hook offset    +$02BE")
    print("BITCNT              $58")
    print("XCUR                $54")
    print("")
    print(
        "R30 option-2 target: replay one text raster row per three source "
        "rows, with native 15/144-inch movement, while leaving the R29 "
        "icon hook unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
