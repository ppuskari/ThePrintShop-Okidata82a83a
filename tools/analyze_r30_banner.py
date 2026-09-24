#!/usr/bin/env python3
r"""Focused R30 banner-text fit analysis for historical Print Shop BDRAW.S.

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


def jsr_occurrences(lines: list[str], target: str) -> list[int]:
    pat = re.compile(r"^\s*JSR\s+" + re.escape(target) + r"\b", re.I)
    return [i for i, line in enumerate(lines) if pat.search(line)]


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
    # The full BSTR text engine matters for row replay: BSTR6 builds the row,
    # SENDGC occurs later, and BSTR15/BSTR16 advance source state.
    bstr12 = find_label(lines, "BSTR12")
    print_lines(lines, max(0, bstr2 - 12), min(len(lines), bstr12 + 45))
    print("")

    print("=== BANNER ICON HOOK ===")
    print_lines(lines, max(0, bicon2 - 16), min(len(lines), bicon2 + 22))
    print("")

    print("=== SENDGC REFERENCES IN BDRAW.S ===")
    sendgc = jsr_occurrences(lines, "SENDGC")
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

    # R30 replay must hook after the actual row send and before the source
    # row/bit state advances. Report the nearest text SENDGC and everything
    # through BSTR16.
    text_sends = [i for i in sendgc if bstr6 < i < bicon2]
    print("=== REPLAY FIT CHECK ===")
    if len(text_sends) != 1:
        print(
            f"Expected exactly one text JSR SENDGC between BSTR6 and BICON2; "
            f"found {len(text_sends)}"
        )
    else:
        send = text_sends[0]
        bstr15 = find_label(lines, "BSTR15")
        bstr16 = find_label(lines, "BSTR16")
        print(f"text JSR SENDGC: line {send + 1}")
        print(f"BSTR15 source-advance gate: line {bstr15 + 1}")
        print(f"BSTR16 continuation: line {bstr16 + 1}")
        print("Post-SENDGC through source advance:")
        print_lines(lines, send - 10, bstr16 + 18)
        print("")
        if send < bstr15:
            print(
                "PASS: the text row is sent before BSTR15 advances BITCNT/"
                "SADDR. A duplicate-row hook can execute after SENDGC while "
                "the source-row state is still current."
            )
        else:
            print(
                "FAIL: source-row state advances before or at SENDGC; direct "
                "row replay would require reconstruction."
            )

    print("")
    print("=== R30 BYTE BUDGET BEFORE SOURCE RECLAIM ===")
    print(
        "BSTR6 fixed hook site: 7 bytes are truly text-local."
    )
    print(
        "The 8-byte EOF helper ($7BF4-$7BFB) is shared: icon enters at "
        "$7BF4 and text enters at $7BF8. Those bytes may be redesigned only "
        "if the hardware-good R29 icon mapping remains semantically identical."
    )
    print(
        "Historical BSTR2 spacing setup is another 7-byte site "
        "(LDX #10 / LDY #0 / JSR CRLF). If the source flow proves that setup "
        "is obsolete under native-feed row replay, those bytes can host "
        "initialization/trampoline logic without shifting addresses."
    )
    print(
        "Practical option-2 fit threshold: there are 7 text-local bytes, "
        "8 constrained shared-helper bytes, and potentially 7 BSTR2 bytes. "
        "That is at most 22 fragmented bytes, but the shared eight must still "
        "preserve the R29 icon result. If row replay needs only an existing "
        "output entry plus compact feed/selection logic, this may fit. If the "
        "row must be rebuilt or font shift state restored, it will not."
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
