#!/usr/bin/env python3
"""Build a runnable Print Shop OkiGraph I runtime disk.

The base image is the DOS 3.4 Color Print Shop runtime whose PRCOMS,
MENUS7, and DRAW1 (GCDRAW.S) binaries exactly match the 1987-01-26 source
snapshot when assembled with Merlin32.

R14 also applies one layout-preserving six-byte patch to the original SYSLIB
TEST PAPER POSITION routine.  The historical routine ends by jumping through
PRCOMS CRLF ($1803), which advances the paper after the alignment dots.  R14
returns the carriage with a raw CR through $1800 instead and does not feed
the paper.

This tool does not redistribute the base disk.  It either reads --base-disk
or downloads the known archive image, verifies the original overlays
byte-for-byte, then rewrites those files in place through their existing
DOS T/S chains.

The compiled overlay arguments are raw Merlin32 output bytes, not DOS binary
headers.  Existing DOS binary load addresses and catalog metadata are
preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
from inspect_printshop_source import SECTOR_SIZE, SECTORS, catalog, fetch, file_sectors
from patch_printshop_source import find_entry, file_sector_locations

BASE_URL = (
    "https://mirrors.apple2.org.za/ftp.apple.asimov.net/"
    "images/productivity/graphics/printshop/ColorPrintShop.DSK"
)

EXPECTED_IMAGE_SIZE = 35 * 16 * 256

# SYSLIB loads at $8800.  TEST PAPER POSITION is entered through $8803,
# which jumps to $88CC.  Its historical epilogue at $88FA is:
#
#   INX
#   LDY #$01
#   JMP $1803       ; PRCOMS CRLF -> carriage return  line feed
#
# R14 changes only those six bytes to:
#
#   LDA #$0D
#   JMP $1800       ; PRCOMS raw character output
#   NOP             ; keep the runtime image exactly length-preserving
#
# This lets repeated paper-position tests overprint the same vertical
# position while the operator micro-adjusts the tractor paper.
TEST_PAPER_LOAD = 0x8800
TEST_PAPER_OFFSET = 0x00FA
TEST_PAPER_OLD = bytes.fromhex("E8 A0 01 4C 03 18")
TEST_PAPER_NEW = bytes.fromhex("A9 0D 4C 00 18 EA")

# R28 banner aspect-ratio helpers live in the resident SYSLIB tail.  Every
# print overlay already calls GETBTNS at $8840, so SYSLIB is resident while
# DRAW4 is running.  The historical SYSLIB payload is 4773 bytes at $8800
# and its existing DOS allocation has room for 87 more payload bytes.
SYSLIB_BASE_LENGTH = 4773

# BSTR6 helper:
#   non-type-5: preserve X=0 and tail-call normal CRLF
#   type-5: X = BITCNT-1, yielding over 8 source rows:
#     six ordinary 24/144 feeds + one 0-feed overstrike + one 15/144 native
#     feed = 159/144 inch versus the historical target 160/144 inch.
BANNER_TEXT_HELPER_BYTES = bytes.fromhex(
    "AD F1 95 C9 05 D0 03 A6 58 CA 4C 03 18"
)

# BICON2 helper:
#   non-type-5: preserve the historical X=6/7 request
#   type-5: every eighth source slice uses X=2 (zero feed), the other seven
#   use X=0 (native 15/144 feed).  Average = 13.125/144 inch versus the
#   historical alternating 12/14 average of 13/144 inch.
BANNER_ICON_HELPER_BYTES = bytes.fromhex(
    "AD F1 95 C9 05 D0 0A A2 00 A5 54 29 07 D0 02 E8 E8 4C 03 18"
)

BANNER_TEXT_CALL = bytes.fromhex("A2 00 A0 01 20 03 18")
BANNER_ICON_CALL = bytes.fromhex("A9 01 A8 25 54 09 06 AA 20 03 18")

EXPECTED_ORIGINAL = {
    "PRCOMS": {
        "load": 0x1800,
        "length": 1962,
        "sha256": "6fb3928799f085967822362a3e7ba0b88dadd21e7e33372951e5734578c4629a",
    },
    "MENUS7": {
        "length": 3014,
        "sha256": "86d7fa76bfd693d461aa9085e3612253837e7f5f02a6027581beef3284c5355f",
    },
    "DRAW1": {
        "load": 0x7800,
        "length": 2737,
        "sha256": "cfa548eb4f950156c14639372f2681edbaa810e86f0945d73c24e0304e436353",
    },
    "DRAW4": {
        "load": 0x7800,
        "length": 1012,
        "sha256": "787a97a6b6441724da019edf6ec586df3cf56acc61047db0b402553ac03699e4",
    },
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_base() -> bytes:
    # Reuse the historical-archive fetcher so Windows Python also gets the
    # narrowly scoped HTTPS-certificate fallback for mirrors.apple2.org.za.
    return fetch(BASE_URL)


def read_dos_binary(img: bytes, name: str) -> tuple[int, bytes]:
    entry = find_entry(img, name)
    raw = file_sectors(img, entry)
    if len(raw) < 4:
        raise RuntimeError(f"{name}: DOS binary shorter than 4-byte header")

    load = raw[0] | (raw[1] << 8)
    length = raw[2] | (raw[3] << 8)
    if length > len(raw) - 4:
        raise RuntimeError(
            f"{name}: binary header length {length} exceeds allocated data"
        )
    return load, raw[4:4 + length]


def verify_original(img: bytes) -> None:
    for name, expect in EXPECTED_ORIGINAL.items():
        load, payload = read_dos_binary(img, name)
        if len(payload) != expect["length"]:
            raise RuntimeError(
                f"{name}: expected {expect['length']} bytes, got {len(payload)}"
            )
        digest = sha256(payload)
        if digest != expect["sha256"]:
            raise RuntimeError(
                f"{name}: base runtime does not match the known source build; "
                f"expected {expect['sha256']}, got {digest}"
            )
        if "load" in expect and load != expect["load"]:
            raise RuntimeError(
                f"{name}: expected load address 0x{expect['load']:04X}, "
                f"got 0x{load:04X}"
            )
        print(
            f"  base {name}: PASS "
            f"load=0x{load:04X} len={len(payload)} sha256={digest}"
        )


def rewrite_dos_binary(img: bytes, name: str, payload: bytes) -> bytes:
    entry = find_entry(img, name)
    raw = file_sectors(img, entry)
    if len(raw) < 4:
        raise RuntimeError(f"{name}: DOS binary shorter than 4-byte header")

    load = raw[0] | (raw[1] << 8)
    old_len = raw[2] | (raw[3] << 8)

    locations = file_sector_locations(img, entry)
    capacity = len(locations) * SECTOR_SIZE
    packed = (
        load.to_bytes(2, "little")
        + len(payload).to_bytes(2, "little")
        + payload
    )
    if len(packed) > capacity:
        raise RuntimeError(
            f"{name}: {len(packed)} bytes exceed existing allocation {capacity}"
        )

    # Preserve any post-EOF bytes in the final allocated sector(s), rather than
    # zeroing them.  Only the binary header/payload bytes change.
    existing = bytearray()
    for trk, sec in locations:
        start = (trk * SECTORS + sec) * SECTOR_SIZE
        existing += img[start:start + SECTOR_SIZE]
    existing[:len(packed)] = packed

    out = bytearray(img)
    for index, (trk, sec) in enumerate(locations):
        start = (trk * SECTORS + sec) * SECTOR_SIZE
        src = index * SECTOR_SIZE
        out[start:start + SECTOR_SIZE] = existing[src:src + SECTOR_SIZE]

    return bytes(out)


def _all_offsets(data: bytes, pattern: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        pos = data.find(pattern, start)
        if pos < 0:
            return offsets
        offsets.append(pos)
        start = pos + 1


def install_banner_helpers(
    img: bytes,
) -> tuple[bytes, int, int, bytes]:
    """Append R28 type-5-only banner helpers to resident SYSLIB."""
    load, payload = read_dos_binary(img, "SYSLIB")
    if load != TEST_PAPER_LOAD:
        raise RuntimeError(
            f"SYSLIB: expected load address 0x{TEST_PAPER_LOAD:04X}, "
            f"got 0x{load:04X}"
        )
    if len(payload) != SYSLIB_BASE_LENGTH:
        raise RuntimeError(
            f"SYSLIB: expected base payload {SYSLIB_BASE_LENGTH} bytes, "
            f"got {len(payload)}"
        )

    entry = find_entry(img, "SYSLIB")
    capacity = len(file_sector_locations(img, entry)) * SECTOR_SIZE - 4

    text_addr = load + len(payload)
    icon_addr = text_addr + len(BANNER_TEXT_HELPER_BYTES)
    patched_payload = (
        payload
        + BANNER_TEXT_HELPER_BYTES
        + BANNER_ICON_HELPER_BYTES
    )
    if len(patched_payload) > capacity:
        raise RuntimeError(
            f"SYSLIB: R28 payload {len(patched_payload)} exceeds "
            f"existing payload capacity {capacity}"
        )

    out = rewrite_dos_binary(img, "SYSLIB", patched_payload)
    check_load, check_payload = read_dos_binary(out, "SYSLIB")
    if check_load != load or check_payload != patched_payload:
        raise RuntimeError("SYSLIB: R28 helper append read-back failed")

    print(
        "  installed R28 resident banner helpers: PASS "
        f"text=0x{text_addr:04X} icon=0x{icon_addr:04X} "
        f"len={len(patched_payload)}"
    )
    return out, text_addr, icon_addr, patched_payload


def patch_banner_draw4(
    img: bytes,
    text_addr: int,
    icon_addr: int,
) -> tuple[bytes, bytes]:
    """Redirect only DRAW4 banner CRLF sites through R28 resident helpers."""
    load, payload = read_dos_binary(img, "DRAW4")
    expect = EXPECTED_ORIGINAL["DRAW4"]
    if load != expect["load"] or len(payload) != expect["length"]:
        raise RuntimeError("DRAW4: unexpected load address or payload length")
    if sha256(payload) != expect["sha256"]:
        raise RuntimeError("DRAW4: base payload hash mismatch")

    text_hits = _all_offsets(payload, BANNER_TEXT_CALL)
    icon_hits = _all_offsets(payload, BANNER_ICON_CALL)
    if len(text_hits) != 1:
        raise RuntimeError(
            f"DRAW4: expected one BSTR6 CRLF site, found {len(text_hits)}"
        )
    if len(icon_hits) != 1:
        raise RuntimeError(
            f"DRAW4: expected one BICON2 CRLF site, found {len(icon_hits)}"
        )

    patched = bytearray(payload)

    # BSTR6: A2 00 A0 01 20 03 18
    text_jsr = text_hits[0] + 4
    if patched[text_jsr] != 0x20:
        raise RuntimeError("DRAW4: BSTR6 JSR opcode mismatch")
    patched[text_jsr + 1:text_jsr + 3] = text_addr.to_bytes(2, "little")

    # BICON2: A9 01 A8 25 54 09 06 AA 20 03 18
    icon_jsr = icon_hits[0] + 8
    if patched[icon_jsr] != 0x20:
        raise RuntimeError("DRAW4: BICON2 JSR opcode mismatch")
    patched[icon_jsr + 1:icon_jsr + 3] = icon_addr.to_bytes(2, "little")

    patched_payload = bytes(patched)
    out = rewrite_dos_binary(img, "DRAW4", patched_payload)
    check_load, check_payload = read_dos_binary(out, "DRAW4")
    if check_load != load or check_payload != patched_payload:
        raise RuntimeError("DRAW4: R28 patch read-back failed")

    print(
        "  patched DRAW4 banner aspect helpers: PASS "
        f"BSTR6+0x{text_hits[0]:04X}->0x{text_addr:04X} "
        f"BICON2+0x{icon_hits[0]:04X}->0x{icon_addr:04X} "
        f"sha256={sha256(patched_payload)}"
    )
    return out, patched_payload


def patch_test_paper_cr_only(img: bytes) -> bytes:
    """Remove only the post-dot line feed from TEST PAPER POSITION."""
    load, payload = read_dos_binary(img, "SYSLIB")
    if load != TEST_PAPER_LOAD:
        raise RuntimeError(
            f"SYSLIB: expected load address 0x{TEST_PAPER_LOAD:04X}, "
            f"got 0x{load:04X}"
        )

    end = TEST_PAPER_OFFSET + len(TEST_PAPER_OLD)
    if end > len(payload):
        raise RuntimeError("SYSLIB: TEST PAPER POSITION patch is out of range")

    found = payload[TEST_PAPER_OFFSET:end]
    if found != TEST_PAPER_OLD:
        raise RuntimeError(
            "SYSLIB: TEST PAPER POSITION epilogue does not match the "
            f"known original bytes; expected {TEST_PAPER_OLD.hex(' ')}, "
            f"got {found.hex(' ')}"
        )

    patched = bytearray(payload)
    patched[TEST_PAPER_OFFSET:end] = TEST_PAPER_NEW
    patched_payload = bytes(patched)

    out = rewrite_dos_binary(img, "SYSLIB", patched_payload)

    check_load, check_payload = read_dos_binary(out, "SYSLIB")
    if check_load != TEST_PAPER_LOAD or check_payload != patched_payload:
        raise RuntimeError("SYSLIB: TEST PAPER POSITION patch read-back failed")

    print(
        "  patched SYSLIB TEST PAPER POSITION: PASS "
        f"0x{TEST_PAPER_LOAD + TEST_PAPER_OFFSET:04X} "
        f"{TEST_PAPER_OLD.hex(' ')} -> {TEST_PAPER_NEW.hex(' ')}"
    )
    return out


def verify_patched(img: bytes, expected: dict[str, bytes]) -> None:
    for name, expected_payload in expected.items():
        load, payload = read_dos_binary(img, name)
        digest = sha256(payload)
        if payload != expected_payload:
            raise RuntimeError(
                f"{name}: patched read-back mismatch "
                f"len={len(payload)} sha256={digest}"
            )
        print(
            f"  patched {name}: PASS "
            f"load=0x{load:04X} len={len(payload)} sha256={digest}"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base-disk",
        type=pathlib.Path,
        help="use a local ColorPrintShop.DSK instead of downloading",
    )
    ap.add_argument("--prcoms", type=pathlib.Path, required=True)
    ap.add_argument("--menus7", type=pathlib.Path, required=True)
    ap.add_argument(
        "--gcdraw",
        type=pathlib.Path,
        required=True,
        help="compiled GCDRAW.OKI payload; installed as runtime DRAW1",
    )
    ap.add_argument("--output", type=pathlib.Path, required=True)
    args = ap.parse_args()

    img = args.base_disk.read_bytes() if args.base_disk else fetch_base()
    if len(img) != EXPECTED_IMAGE_SIZE:
        raise RuntimeError(
            f"base image must be {EXPECTED_IMAGE_SIZE} bytes; got {len(img)}"
        )

    entries = {e["name"].upper(): e for e in catalog(img)}
    for required in ("PRCOMS", "MENUS7", "DRAW1", "DRAW4", "SYSLIB"):
        if required not in entries:
            raise RuntimeError(f"base disk is missing required file {required}")

    print("Validating exact Print Shop runtime base...")
    verify_original(img)

    prcoms = args.prcoms.read_bytes()
    menus7 = args.menus7.read_bytes()
    gcdraw = args.gcdraw.read_bytes()

    print(
        f"  input PRCOMS len={len(prcoms)} sha256={sha256(prcoms)}"
    )
    print(
        f"  input MENUS7 len={len(menus7)} sha256={sha256(menus7)}"
    )
    print(
        f"  input GCDRAW/DRAW1 len={len(gcdraw)} sha256={sha256(gcdraw)}"
    )

    print("Rewriting executable overlays in place...")
    img = rewrite_dos_binary(img, "PRCOMS", prcoms)
    img = rewrite_dos_binary(img, "MENUS7", menus7)
    img = rewrite_dos_binary(img, "DRAW1", gcdraw)

    print("Patching TEST PAPER POSITION to return carriage without line feed...")
    img = patch_test_paper_cr_only(img)

    print("Installing R28 resident banner aspect-ratio helpers...")
    img, banner_text_addr, banner_icon_addr, syslib_r28 = install_banner_helpers(
        img
    )

    print("Redirecting DRAW4 banner raster spacing through R28 helpers...")
    img, draw4_r28 = patch_banner_draw4(
        img, banner_text_addr, banner_icon_addr
    )

    print("Reading patched overlays back through DOS T/S chains...")
    verify_patched(
        img,
        {
            "PRCOMS": prcoms,
            "MENUS7": menus7,
            "DRAW1": gcdraw,
            "DRAW4": draw4_r28,
            "SYSLIB": syslib_r28,
        },
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(img)

    digest = sha256(img)
    print(f"Runtime image: {args.output}")
    print(f"Image bytes: {len(img)}")
    print(f"Image SHA256: {digest}")
    print("PASS: runnable DOS disk image constructed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
