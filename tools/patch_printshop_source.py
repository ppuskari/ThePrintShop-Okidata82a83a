#!/usr/bin/env python3
"""Create the first Print Shop v2 source-level OkiGraph I driver patch.

v0.1 intentionally repurposes the existing printer-type-5
"OKIDATA MICROLINE 92,93" path.  It changes only:

* the menu label (same character count), and
* the type-5 graphics-byte emission block (same assembled byte count).

The historical Brøderbund source is fetched or read locally but is never
stored in this repository.  --check validates that the expected source
snapshot still matches.  --output-dir emits decoded patched source files for
local assembly/import.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import urllib.parse

from inspect_printshop_source import BASE, NAMES, catalog, fetch, file_sectors

OLD_MENU = "OKIDATA MICROLINE 92,93"
NEW_MENU = "OKI 82A/83A OKIGRAPH I "

# Keep the replacement machine-code length equal to the original.
# Original byte count:
#   PLA(1)+ORA zp(2)+STX zp(2)+JSR(3)+LDX zp(2)+JSR(3)
#   +CMP #(2)+BNE(2)+JSR(3) = 20
# Replacement:
#   PLA(1)+ORA zp(2)+STX zp(2)+JSR(3)+ORA #(2)+LDX zp(2)+JSR(3)
#   +5*NOP(5) = 20
GC5_OLD = re.compile(
    r"(?m)^GC5A PLA\n"
    r"[ \t]+ORA GCOLD\n"
    r"[ \t]+STX XTEMP\n"
    r"[ \t]+JSR REVBITS\n"
    r"[ \t]+LDX XTEMP\n"
    r"[ \t]+JSR COUT1\n"
    r"[ \t]+CMP #03\n"
    r"[ \t]+BNE GC5B\n"
    r"[ \t]+JSR COUT1\n"
    r"^GC5B PHA$"
)

GC5_NEW = """GC5A PLA
 ORA GCOLD
 STX XTEMP
 JSR REVBITS
 ORA #$80
 LDX XTEMP
 JSR COUT1
 NOP
 NOP
 NOP
 NOP
 NOP
GC5B PHA"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("ascii", "replace")).hexdigest()


def find_entry(img: bytes, wanted: str):
    for entry in catalog(img):
        if entry["name"].upper() == wanted.upper():
            return entry
    raise RuntimeError(f"{wanted!r} not found in DOS 3.3 catalog")


def binary_source_text(img: bytes, name: str) -> str:
    raw = file_sectors(img, find_entry(img, name))

    # The source files are DOS 3.3 binary files.  Prefer the standard
    # load-address/length header when it is plausible; otherwise retain the
    # sector stream so the matcher still fails explicitly rather than hiding
    # a format change.
    payload = raw
    if len(raw) >= 4:
        length = raw[2] | (raw[3] << 8)
        if 0 < length <= len(raw) - 4:
            payload = raw[4:4 + length]

    payload = bytes(b & 0x7F for b in payload)
    return (
        payload.decode("ascii", "replace")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\x00", "\n")
    )


def replace_once(text: str, old: str, new: str, what: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{what}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_prcoms(text: str) -> str:
    matches = list(GC5_OLD.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(
            "PRCOMS.S GC5 block: expected exactly one legacy type-5 block, "
            f"found {len(matches)}"
        )
    return GC5_OLD.sub(GC5_NEW, text, count=1)


def patch_menus(text: str) -> str:
    if len(OLD_MENU) != len(NEW_MENU):
        raise AssertionError("menu replacement must remain length-preserving")
    return replace_once(text, OLD_MENU, NEW_MENU, "MENUS7.S printer label")


def load_image(path: pathlib.Path | None, disk_index: int) -> bytes:
    if path is not None:
        data = path.read_bytes()
        return data
    name = NAMES[disk_index]
    return fetch(BASE + urllib.parse.quote(name))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disk1", type=pathlib.Path,
                    help="local source disk 1 .dsk instead of downloading")
    ap.add_argument("--disk2", type=pathlib.Path,
                    help="local source disk 2 .dsk instead of downloading")
    ap.add_argument("--output-dir", type=pathlib.Path,
                    help="emit decoded patched PRCOMS/MENUS7 source")
    ap.add_argument("--check", action="store_true",
                    help="validate patch applicability without requiring output")
    args = ap.parse_args()

    disk1 = load_image(args.disk1, 0)
    disk2 = load_image(args.disk2, 1)

    prcoms = binary_source_text(disk1, "PRCOMS.S")
    menus7 = binary_source_text(disk2, "MENUS7.S")

    patched_prcoms = patch_prcoms(prcoms)
    patched_menus7 = patch_menus(menus7)

    # The source transformation is designed so the affected assembled regions
    # do not move: 23 menu characters replace 23 characters, and the GC5
    # machine-code block remains 20 bytes.
    assert len(OLD_MENU) == len(NEW_MENU) == 23

    print("Print Shop v2 OkiGraph I source patch: PASS")
    print("  printer type: 5 (repurposed legacy Okidata 92/93 path)")
    print("  menu label: 23 -> 23 characters")
    print("  GC5 machine-code block: 20 -> 20 bytes by construction")
    print("  graphics data: reverse7(pair OR) | $80")
    print("  framing: existing $03 ... $03 $02 retained")
    print(f"  PRCOMS decoded SHA256 before: {sha256_text(prcoms)}")
    print(f"  PRCOMS decoded SHA256 after : {sha256_text(patched_prcoms)}")
    print(f"  MENUS7 decoded SHA256 before: {sha256_text(menus7)}")
    print(f"  MENUS7 decoded SHA256 after : {sha256_text(patched_menus7)}")

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "PRCOMS.OKI.S").write_text(
            patched_prcoms, encoding="ascii", newline="\n"
        )
        (args.output_dir / "MENUS7.OKI.S").write_text(
            patched_menus7, encoding="ascii", newline="\n"
        )
        print(f"  wrote decoded patched source to: {args.output_dir}")

    if not args.check and not args.output_dir:
        print("  note: use --output-dir build to emit patched decoded source")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
