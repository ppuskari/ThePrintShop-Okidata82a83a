#!/usr/bin/env python3
"""Build a runnable Print Shop OkiGraph I runtime disk.

R29 starts from the hardware-good R27 runtime.  PRCOMS, MENUS7, DRAW1,
and the R14 SYSLIB paper-position patch remain the R27 versions.

Banner geometry is implemented only in the BDRAW/DRAW4 overlay.  Because the
patched DRAW4 is larger than its historical four data sectors, this builder
may allocate one additional DOS 3.3 data sector to DRAW4.  The overlay still
loads at $7800 and is required to end below $8300.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib

from inspect_printshop_source import (
    SECTOR_SIZE,
    SECTORS,
    catalog,
    dos_name,
    fetch,
    file_sectors,
    sector,
)
from patch_printshop_source import find_entry, file_sector_locations

BASE_URL = (
    "https://mirrors.apple2.org.za/ftp.apple.asimov.net/"
    "images/productivity/graphics/printshop/ColorPrintShop.DSK"
)

TRACKS = 35
EXPECTED_IMAGE_SIZE = TRACKS * SECTORS * SECTOR_SIZE

TEST_PAPER_LOAD = 0x8800
TEST_PAPER_OFFSET = 0x00FA
TEST_PAPER_OLD = bytes.fromhex("E8 A0 01 4C 03 18")
TEST_PAPER_NEW = bytes.fromhex("A9 0D 4C 00 18 EA")
SYSLIB_BASE_LENGTH = 4773

DRAW_OVERLAY_LIMIT = 0x8300

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


BANNER_TEXT_CALL = bytes.fromhex("A2 00 A0 01 20 03 18")
BANNER_ICON_CALL = bytes.fromhex(
    "A9 01 A8 25 54 09 06 AA 20 03 18"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_base() -> bytes:
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
                f"{name}: base runtime mismatch; expected "
                f"{expect['sha256']}, got {digest}"
            )
        if load != expect["load"]:
            raise RuntimeError(
                f"{name}: expected load 0x{expect['load']:04X}, "
                f"got 0x{load:04X}"
            )
        print(
            f"  base {name}: PASS load=0x{load:04X} "
            f"len={len(payload)} sha256={digest}"
        )


def _sector_offset(track: int, sec: int) -> int:
    return (track * SECTORS + sec) * SECTOR_SIZE


def _ts_list_sectors(img: bytes, entry) -> list[tuple[int, int]]:
    trk, sec = entry["ts_track"], entry["ts_sector"]
    seen: set[tuple[int, int]] = set()
    result: list[tuple[int, int]] = []
    while trk:
        key = (trk, sec)
        if key in seen:
            raise RuntimeError(f"T/S-list loop in {entry['name']}")
        seen.add(key)
        result.append(key)
        ts = sector(img, trk, sec)
        trk, sec = ts[1], ts[2]
    return result


def _catalog_entry_offset(img: bytes, wanted: str) -> int:
    vtoc = sector(img, 17, 0)
    trk, sec = vtoc[1], vtoc[2]
    seen: set[tuple[int, int]] = set()

    while trk:
        key = (trk, sec)
        if key in seen:
            raise RuntimeError("catalog T/S loop")
        seen.add(key)
        cat = sector(img, trk, sec)
        next_trk, next_sec = cat[1], cat[2]
        base = _sector_offset(trk, sec)

        for off in range(0x0B, 0x100 - 34, 35):
            ent = cat[off:off + 35]
            if ent[0] in (0x00, 0xFF):
                continue
            if dos_name(ent[3:33]).upper() == wanted.upper():
                return base + off

        trk, sec = next_trk, next_sec

    raise RuntimeError(f"catalog entry {wanted!r} not found")


def _vtoc_bitmap_offset(track: int, sec: int) -> tuple[int, int]:
    if not (0 <= track < TRACKS and 0 <= sec < SECTORS):
        raise ValueError("invalid VTOC sector coordinate")
    # DOS 3.3 bitmap byte 0 maps sectors F..8 to bits 7..0;
    # byte 1 maps sectors 7..0 to bits 7..0. A set bit means free.
    if sec >= 8:
        byte_index = 0
        bit_index = sec - 8
    else:
        byte_index = 1
        bit_index = sec
    byte_off = 0x38 + track * 4 + byte_index
    mask = 1 << bit_index
    return _sector_offset(17, 0) + byte_off, mask


def _vtoc_sector_is_free(img: bytes, track: int, sec: int) -> bool:
    off, mask = _vtoc_bitmap_offset(track, sec)
    return bool(img[off] & mask)


def _referenced_sectors(img: bytes) -> set[tuple[int, int]]:
    used: set[tuple[int, int]] = set()

    # DOS boot/system tracks and the VTOC/catalog track are never candidates.
    for trk in (0, 1, 2, 17):
        for sec in range(SECTORS):
            used.add((trk, sec))

    for entry in catalog(img):
        used.update(_ts_list_sectors(img, entry))
        used.update(file_sector_locations(img, entry))

    return used


def _find_free_sector(img: bytes) -> tuple[int, int]:
    used = _referenced_sectors(img)

    # Prefer the high tracks so DRAW4 growth stays away from DOS/system areas.
    for trk in range(TRACKS - 1, 2, -1):
        if trk == 17:
            continue
        for sec in range(SECTORS - 1, -1, -1):
            if (trk, sec) in used:
                continue
            if _vtoc_sector_is_free(img, trk, sec):
                return trk, sec

    raise RuntimeError("no free DOS sector available for DRAW4 growth")


def _grow_file_one_data_sector(img: bytes, name: str) -> bytes:
    entry = find_entry(img, name)
    ts_chain = _ts_list_sectors(img, entry)
    last_trk, last_sec = ts_chain[-1]
    last_start = _sector_offset(last_trk, last_sec)

    pair_offset = None
    last_ts = sector(img, last_trk, last_sec)
    last_nonzero = None
    for off in range(0x0C, 0x100 - 1, 2):
        if last_ts[off] != 0:
            last_nonzero = off
    pair_offset = 0x0C if last_nonzero is None else last_nonzero + 2
    if pair_offset >= 0x100 - 1:
        raise RuntimeError(
            f"{name}: last T/S-list sector has no free data-sector slot"
        )

    new_trk, new_sec = _find_free_sector(img)
    out = bytearray(img)

    # Add the new data sector to the existing final T/S list.
    out[last_start + pair_offset] = new_trk
    out[last_start + pair_offset + 1] = new_sec

    # Mark it allocated in the DOS 3.3 VTOC bitmap.
    vtoc_off, mask = _vtoc_bitmap_offset(new_trk, new_sec)
    if not (out[vtoc_off] & mask):
        raise RuntimeError(
            f"candidate sector {new_trk}/{new_sec} was not free in VTOC"
        )
    out[vtoc_off] &= (~mask) & 0xFF

    # Keep the catalog sector-count field consistent.
    cat_off = _catalog_entry_offset(img, name)
    old_count = out[cat_off + 33] | (out[cat_off + 34] << 8)
    new_count = old_count + 1
    out[cat_off + 33] = new_count & 0xFF
    out[cat_off + 34] = (new_count >> 8) & 0xFF

    # Start the newly allocated sector clean.
    data_off = _sector_offset(new_trk, new_sec)
    out[data_off:data_off + SECTOR_SIZE] = bytes(SECTOR_SIZE)

    print(
        f"  expanded {name}: added DOS data sector "
        f"T{new_trk:02d}/S{new_sec:02d}; catalog sectors "
        f"{old_count}->{new_count}"
    )
    return bytes(out)


def _ensure_binary_capacity(
    img: bytes,
    name: str,
    packed_length: int,
) -> bytes:
    out = img
    while True:
        entry = find_entry(out, name)
        capacity = len(file_sector_locations(out, entry)) * SECTOR_SIZE
        if packed_length <= capacity:
            return out
        out = _grow_file_one_data_sector(out, name)


def rewrite_dos_binary(
    img: bytes,
    name: str,
    payload: bytes,
    *,
    allow_expand: bool = False,
) -> bytes:
    entry = find_entry(img, name)
    raw = file_sectors(img, entry)
    if len(raw) < 4:
        raise RuntimeError(f"{name}: DOS binary shorter than 4-byte header")

    load = raw[0] | (raw[1] << 8)
    packed = (
        load.to_bytes(2, "little")
        + len(payload).to_bytes(2, "little")
        + payload
    )

    out_img = img
    locations = file_sector_locations(out_img, find_entry(out_img, name))
    capacity = len(locations) * SECTOR_SIZE

    if len(packed) > capacity:
        if not allow_expand:
            raise RuntimeError(
                f"{name}: {len(packed)} bytes exceed existing "
                f"allocation {capacity}"
            )
        out_img = _ensure_binary_capacity(out_img, name, len(packed))
        locations = file_sector_locations(
            out_img, find_entry(out_img, name)
        )
        capacity = len(locations) * SECTOR_SIZE

    existing = bytearray()
    for trk, sec in locations:
        start = _sector_offset(trk, sec)
        existing += out_img[start:start + SECTOR_SIZE]

    existing[:len(packed)] = packed

    out = bytearray(out_img)
    for index, (trk, sec) in enumerate(locations):
        start = _sector_offset(trk, sec)
        src = index * SECTOR_SIZE
        out[start:start + SECTOR_SIZE] = existing[src:src + SECTOR_SIZE]

    return bytes(out)


class _HelperBuilder:
    def __init__(self, base: int):
        self.base = base
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.rel8: list[tuple[int, str]] = []
        self.abs16: list[tuple[int, str]] = []

    def emit(self, *values: int) -> None:
        self.code.extend(values)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise RuntimeError(f"duplicate helper label {name}")
        self.labels[name] = len(self.code)

    def branch(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0)
        self.rel8.append((len(self.code) - 1, label))

    def abs_label(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0, 0)
        self.abs16.append((len(self.code) - 2, label))

    def finish(self) -> bytes:
        for operand_index, label in self.rel8:
            if label not in self.labels:
                raise RuntimeError(f"unknown helper label {label}")
            target = self.base + self.labels[label]
            next_pc = self.base + operand_index + 1
            delta = target - next_pc
            if not -128 <= delta <= 127:
                raise RuntimeError(f"branch to {label} is out of range")
            self.code[operand_index] = delta & 0xFF

        for operand_index, label in self.abs16:
            if label not in self.labels:
                raise RuntimeError(f"unknown helper label {label}")
            target = self.base + self.labels[label]
            self.code[operand_index] = target & 0xFF
            self.code[operand_index + 1] = (target >> 8) & 0xFF

        return bytes(self.code)


def _build_banner_text_helper(base: int) -> bytes:
    """Build type-5 banner-text 1,1,2 native-feed helper."""
    a = _HelperBuilder(base)

    # Call site already loaded X=0,Y=1. Non-type-5 printers simply tail-call
    # the original CRLF. Type 5 changes only Y according to a 1,1,2 cadence.
    a.emit(0xAD, 0xF1, 0x95)       # LDA $95F1 (PRTYPE)
    a.emit(0xC9, 0x05)             # CMP #5
    a.branch(0xD0, "pass")          # BNE pass
    a.abs_label(0xEE, "phase")      # INC phase
    a.abs_label(0xAD, "phase")      # LDA phase
    a.emit(0xC9, 0x03)             # CMP #3
    a.branch(0x90, "one")           # BCC one
    a.emit(0xA9, 0x00)             # LDA #0
    a.abs_label(0x8D, "phase")      # STA phase
    a.emit(0xA0, 0x02)             # LDY #2
    a.branch(0xD0, "pass")          # BNE pass (always)
    a.label("one")
    a.emit(0xA0, 0x01)             # LDY #1
    a.label("pass")
    a.emit(0x4C, 0x03, 0x18)       # JMP CRLF
    a.label("phase")
    a.emit(0x00)

    return a.finish()


def _build_banner_icon_helper(base: int) -> bytes:
    """Build type-5 15->13 banner-icon positioning helper."""
    a = _HelperBuilder(base)

    # Original BICON2 code has already computed X=6/7,Y=1 before calling us.
    # Preserve that for every non-type-5 printer.
    a.emit(0xAD, 0xF1, 0x95)       # LDA $95F1 (PRTYPE)
    a.emit(0xC9, 0x05)             # CMP #5
    a.branch(0xD0, "pass")          # BNE pass

    a.emit(0xA5, 0x54)             # LDA XCUR
    a.label("mod")
    a.emit(0xC9, 0x0F)             # CMP #15
    a.branch(0x90, "remainder")     # BCC remainder
    a.emit(0xE9, 0x0F)             # SBC #15 (CMP left C set)
    a.branch(0xB0, "mod")           # BCS mod

    a.label("remainder")
    a.emit(0xC9, 0x00)             # CMP #0
    a.branch(0xF0, "merge")         # BEQ merge
    a.emit(0xC9, 0x08)             # CMP #8
    a.branch(0xF0, "merge")         # BEQ merge

    a.emit(0xA2, 0x00)             # LDX #0: native feed
    a.emit(0xA0, 0x01)             # LDY #1
    a.emit(0x4C, 0x03, 0x18)       # JMP CRLF

    a.label("merge")
    a.emit(0xA2, 0x02)             # LDX #2: zero-feed overstrike
    a.emit(0xA0, 0x01)             # LDY #1
    a.emit(0x4C, 0x03, 0x18)       # JMP CRLF

    a.label("pass")
    a.emit(0x4C, 0x03, 0x18)       # JMP original CRLF

    return a.finish()


def patch_banner_draw4_payload(
    payload: bytes,
    load: int = 0x7800,
) -> tuple[bytes, dict[str, int]]:
    """Patch the exact shipped DRAW4 and append banner-only helpers."""
    text_hits = [
        i for i in range(len(payload))
        if payload.startswith(BANNER_TEXT_CALL, i)
    ]
    icon_hits = [
        i for i in range(len(payload))
        if payload.startswith(BANNER_ICON_CALL, i)
    ]

    if len(text_hits) != 1:
        raise RuntimeError(
            f"DRAW4: expected one banner-text CRLF site, found {len(text_hits)}"
        )
    if len(icon_hits) != 1:
        raise RuntimeError(
            f"DRAW4: expected one banner-icon CRLF site, found {len(icon_hits)}"
        )

    text_addr = load + len(payload)
    text_helper = _build_banner_text_helper(text_addr)
    icon_addr = text_addr + len(text_helper)
    icon_helper = _build_banner_icon_helper(icon_addr)

    patched = bytearray(payload)

    text_jsr = text_hits[0] + 4
    if patched[text_jsr] != 0x20:
        raise RuntimeError("DRAW4: banner-text site lost JSR opcode")
    patched[text_jsr + 1] = text_addr & 0xFF
    patched[text_jsr + 2] = (text_addr >> 8) & 0xFF

    icon_jsr = icon_hits[0] + 8
    if patched[icon_jsr] != 0x20:
        raise RuntimeError("DRAW4: banner-icon site lost JSR opcode")
    patched[icon_jsr + 1] = icon_addr & 0xFF
    patched[icon_jsr + 2] = (icon_addr >> 8) & 0xFF

    patched += text_helper
    patched += icon_helper

    return bytes(patched), {
        "text_site": text_hits[0],
        "icon_site": icon_hits[0],
        "text_helper": text_addr,
        "icon_helper": icon_addr,
    }


def patch_banner_draw4(img: bytes) -> tuple[bytes, bytes]:
    load, payload = read_dos_binary(img, "DRAW4")
    expect = EXPECTED_ORIGINAL["DRAW4"]
    if load != expect["load"]:
        raise RuntimeError("DRAW4: unexpected load address")
    if len(payload) != expect["length"] or sha256(payload) != expect["sha256"]:
        raise RuntimeError("DRAW4: runtime base does not match known 1012-byte image")

    patched_payload, info = patch_banner_draw4_payload(payload, load)
    end = load + len(patched_payload)
    if end > DRAW_OVERLAY_LIMIT:
        raise RuntimeError(
            f"R29 DRAW4 would end at 0x{end:04X}, beyond "
            f"0x{DRAW_OVERLAY_LIMIT:04X}"
        )

    out = rewrite_dos_binary(
        img,
        "DRAW4",
        patched_payload,
        allow_expand=True,
    )
    check_load, check_payload = read_dos_binary(out, "DRAW4")
    if check_load != load or check_payload != patched_payload:
        raise RuntimeError("DRAW4: R29 runtime patch read-back failed")

    print(
        "  patched runtime DRAW4 directly: PASS "
        f"text site +0x{info['text_site']:04X} -> "
        f"0x{info['text_helper']:04X}; "
        f"icon site +0x{info['icon_site']:04X} -> "
        f"0x{info['icon_helper']:04X}"
    )
    print(
        f"  R29 DRAW4 len={len(patched_payload)} "
        f"RAM=0x{load:04X}-0x{end - 1:04X} "
        f"sha256={sha256(patched_payload)}"
    )
    return out, patched_payload


def patch_test_paper_cr_only(img: bytes) -> tuple[bytes, bytes]:
    load, payload = read_dos_binary(img, "SYSLIB")
    if load != TEST_PAPER_LOAD:
        raise RuntimeError(
            f"SYSLIB: expected load 0x{TEST_PAPER_LOAD:04X}, "
            f"got 0x{load:04X}"
        )
    if len(payload) != SYSLIB_BASE_LENGTH:
        raise RuntimeError(
            f"SYSLIB: expected exact historical length "
            f"{SYSLIB_BASE_LENGTH}, got {len(payload)}"
        )

    end = TEST_PAPER_OFFSET + len(TEST_PAPER_OLD)
    found = payload[TEST_PAPER_OFFSET:end]
    if found != TEST_PAPER_OLD:
        raise RuntimeError(
            "SYSLIB TEST PAPER POSITION bytes do not match the known base"
        )

    patched = bytearray(payload)
    patched[TEST_PAPER_OFFSET:end] = TEST_PAPER_NEW
    patched_payload = bytes(patched)
    out = rewrite_dos_binary(img, "SYSLIB", patched_payload)

    check_load, check_payload = read_dos_binary(out, "SYSLIB")
    if check_load != load or check_payload != patched_payload:
        raise RuntimeError("SYSLIB paper-position patch read-back failed")
    if len(check_payload) != SYSLIB_BASE_LENGTH:
        raise RuntimeError("R29 must not grow resident SYSLIB")

    print(
        "  patched SYSLIB TEST PAPER POSITION: PASS; "
        f"resident length remains {len(check_payload)} bytes"
    )
    return out, patched_payload


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
            f"  patched {name}: PASS load=0x{load:04X} "
            f"len={len(payload)} sha256={digest}"
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
        help="compiled GCDRAW.OKI payload; installed as DRAW1",
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
            raise RuntimeError(f"base disk missing required file {required}")

    print("Validating exact Print Shop runtime base...")
    verify_original(img)

    prcoms = args.prcoms.read_bytes()
    menus7 = args.menus7.read_bytes()
    gcdraw = args.gcdraw.read_bytes()

    print(f"  input PRCOMS len={len(prcoms)} sha256={sha256(prcoms)}")
    print(f"  input MENUS7 len={len(menus7)} sha256={sha256(menus7)}")
    print(f"  input GCDRAW/DRAW1 len={len(gcdraw)} sha256={sha256(gcdraw)}")

    print("Rewriting R27 executable overlays...")
    img = rewrite_dos_binary(img, "PRCOMS", prcoms)
    img = rewrite_dos_binary(img, "MENUS7", menus7)
    img = rewrite_dos_binary(img, "DRAW1", gcdraw)

    print("Patching exact shipped DRAW4 runtime for R29 banner geometry...")
    img, draw4 = patch_banner_draw4(img)

    print("Applying R14 paper-position patch without growing SYSLIB...")
    img, syslib = patch_test_paper_cr_only(img)

    print("Reading patched overlays back through DOS T/S chains...")
    verify_patched(
        img,
        {
            "PRCOMS": prcoms,
            "MENUS7": menus7,
            "DRAW1": gcdraw,
            "DRAW4": draw4,
            "SYSLIB": syslib,
        },
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(img)

    digest = sha256(img)
    print(f"Runtime image: {args.output}")
    print(f"Image bytes: {len(img)}")
    print(f"Image SHA256: {digest}")
    print("PASS: R29 banner-contained runnable DOS disk constructed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
