#!/usr/bin/env python3
"""Build a runnable Print Shop OkiGraph I runtime disk.

R29 starts from the hardware-good R27 runtime.  PRCOMS, MENUS7, DRAW1,
and the R14 SYSLIB paper-position patch remain the R27 versions.

Banner geometry is implemented only in the runtime DRAW4 overlay. R29 is
strictly allocation- and address-preserving: the 1012-byte shipped payload is
patched at two fixed sites and an eight-byte helper is appended into the
existing fourth sector's EOF slack. The final payload is 1020 bytes, so the
four-byte DOS binary header plus payload exactly fills the existing 1024-byte
allocation. No VTOC, T/S-list, or existing runtime address is changed.
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
    "DRAW3": {
        "load": 0x7800,
        "length": 2811,
        "sha256": "072130b812021e1b586c69951ffcf111ca93043fb97452113954f76d6796a046",
    },
    "DRAW4": {
        "load": 0x7800,
        "length": 1012,
        "sha256": "787a97a6b6441724da019edf6ec586df3cf56acc61047db0b402553ac03699e4",
    },
    "MENUS1": {
        "load": 0x4000,
        "length": 6136,
        "sha256": "a133a2b2c72a970a722ece9f5c03a0823e047b3bc05fece6b14b5c3715f37c40",
    },
    "MENUS3": {
        "load": 0x4000,
        "length": 2584,
        "sha256": "ba570d635de4ebed8f32599146c56ebf975f27ed89e967d220175963d8b7922d",
    },
    "MENUS4": {
        "load": 0x4000,
        "length": 1513,
        "sha256": "b80c97a43d1a89134575f76db5a0f3ce633f523136cffb12f2afa33c21692d58",
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
        expected_hash = expect.get("sha256")
        if expected_hash is not None and digest != expected_hash:
            raise RuntimeError(
                f"{name}: base runtime mismatch; expected "
                f"{expected_hash}, got {digest}"
            )
        if "load" in expect and load != expect["load"]:
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


def _catalog_sectors(img: bytes) -> list[tuple[int, int]]:
    vtoc = sector(img, 17, 0)
    trk, sec = vtoc[1], vtoc[2]
    seen: set[tuple[int, int]] = set()
    result: list[tuple[int, int]] = []
    while trk:
        key = (trk, sec)
        if key in seen:
            raise RuntimeError("catalog sector loop")
        seen.add(key)
        result.append(key)
        cat = sector(img, trk, sec)
        trk, sec = cat[1], cat[2]
    return result


def _referenced_sectors(img: bytes) -> set[tuple[int, int]]:
    used: set[tuple[int, int]] = set()

    # DOS boot/system tracks and the VTOC/catalog track are never candidates.
    for trk in (0, 1, 2, 17):
        for sec in range(SECTORS):
            used.add((trk, sec))

    used.update(_catalog_sectors(img))

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


R31_CATALOG_SECTOR = (32, 9)
R31_OVERLAY_SECTORS = (
    tuple((34, sec) for sec in range(16))
    + ((32, 10),)
)
R31_RECLAIM_SECTORS = R31_OVERLAY_SECTORS + (R31_CATALOG_SECTOR,)


def _deleted_mainmenu_track(img: bytes) -> int | None:
    """Return DOS's saved T/S track for the deleted MAINMENU entry."""
    vtoc = sector(img, 17, 0)
    trk, sec = vtoc[1], vtoc[2]
    seen: set[tuple[int, int]] = set()
    found: list[int] = []

    while trk:
        key = (trk, sec)
        if key in seen:
            raise RuntimeError("catalog loop in deleted MAINMENU audit")
        seen.add(key)
        cat = sector(img, trk, sec)
        next_trk, next_sec = cat[1], cat[2]

        for off in range(0x0B, 0x100 - 34, 35):
            ent = cat[off:off + 35]
            if ent[0] != 0xFF:
                continue
            raw_name = bytes(b & 0x7F for b in ent[3:33])
            display = "".join(
                chr(b) if 32 <= b < 127 else " "
                for b in raw_name
            ).strip()
            if display.startswith("MAINMENU"):
                found.append(ent[32] & 0x7F)

        trk, sec = next_trk, next_sec

    if len(found) != 1:
        raise RuntimeError(
            "R31 reclaim: expected one deleted MAINMENU catalog entry, "
            f"found {len(found)}"
        )
    return found[0]


def reclaim_r31_overlay_sectors(img: bytes) -> bytes:
    """Expose exactly 17 proven-stale sectors for DRAW6/DRAW8 allocation.

    The production disk has no VTOC-free sectors, but it contains two
    independently provable stale regions:

    * Track 34 is an exact sector-for-sector duplicate of live track 16.
      None of its 16 sectors is referenced by any live catalog file.
    * T32/S10 is the T/S-list sector for the single deleted MAINMENU entry.
      Its pairs are the stale T32/S09..S02 chain and it is unreferenced.

    DRAW6 needs 12 sectors (one T/S + eleven data) and DRAW8 needs five
    (one T/S + four data). A second deleted MAINMENU data sector, T32/S09,
    becomes one new catalog sector so both files can have directory entries.
    The resulting reclaim set is exactly 18 sectors: 17 overlay sectors plus
    one catalog sector.
    """
    referenced = _referenced_sectors(img)
    pool = list(R31_RECLAIM_SECTORS)

    # Track 34 must remain a byte-for-byte stale duplicate of track 16.
    for sec in range(SECTORS):
        t34 = sector(img, 34, sec)
        t16 = sector(img, 16, sec)
        if t34 != t16:
            raise RuntimeError(
                f"R31 reclaim: T34/S{sec:02d} no longer matches "
                f"T16/S{sec:02d}"
            )

    # None of the proposed sectors may be live or already marked free.
    for trk, sec in pool:
        if (trk, sec) in referenced:
            raise RuntimeError(
                f"R31 reclaim: T{trk:02d}/S{sec:02d} is live"
            )
        if _vtoc_sector_is_free(img, trk, sec):
            raise RuntimeError(
                f"R31 reclaim: T{trk:02d}/S{sec:02d} unexpectedly "
                "already free"
            )

    # Prove the deleted MAINMENU provenance for T32/S10.
    if _deleted_mainmenu_track(img) != 32:
        raise RuntimeError(
            "R31 reclaim: deleted MAINMENU no longer points at track 32"
        )
    ts = sector(img, 32, 10)
    if ts[1] != 0 or ts[2] != 0:
        raise RuntimeError("R31 reclaim: T32/S10 unexpectedly chains onward")
    if (ts[5] | (ts[6] << 8)) != 0:
        raise RuntimeError(
            "R31 reclaim: T32/S10 has nonzero file-sector offset"
        )
    pairs: list[tuple[int, int]] = []
    for off in range(0x0C, 0x100, 2):
        trk, sec = ts[off], ts[off + 1]
        if trk == 0:
            break
        pairs.append((trk, sec))
    expected_pairs = [(32, sec) for sec in range(9, 1, -1)]
    if pairs != expected_pairs:
        raise RuntimeError(
            "R31 reclaim: deleted MAINMENU T/S list changed; "
            f"expected {expected_pairs}, got {pairs}"
        )

    out = bytearray(img)
    for trk, sec in pool:
        vtoc_off, mask = _vtoc_bitmap_offset(trk, sec)
        out[vtoc_off] |= mask

    result = bytes(out)
    free_now = [
        (trk, sec)
        for trk, sec in pool
        if _vtoc_sector_is_free(result, trk, sec)
    ]
    if free_now != pool:
        raise RuntimeError("R31 reclaim: failed to expose exact sector pool")

    print(
        "  R31 stale-sector reclaim: PASS "
        "T34/S00-S15 duplicate T16; T32/S10 deleted MAINMENU T/S; "
        "18 sectors exposed (17 overlay + 1 catalog)"
    )
    return result


def extend_r31_catalog(img: bytes) -> bytes:
    """Consume T32/S09 as a new final DOS catalog sector."""
    cat_loc = R31_CATALOG_SECTOR
    if not _vtoc_sector_is_free(img, *cat_loc):
        raise RuntimeError(
            "R31 catalog extension sector is not free after reclaim"
        )

    chain = _catalog_sectors(img)
    if not chain:
        raise RuntimeError("R31 catalog extension found empty catalog chain")
    last_trk, last_sec = chain[-1]
    last_off = _sector_offset(last_trk, last_sec)

    out = bytearray(img)
    # Link previous final catalog sector to the new one.
    out[last_off + 1] = cat_loc[0]
    out[last_off + 2] = cat_loc[1]

    # Allocate and clear the new catalog sector. All-zero entry slots are free.
    vtoc_off, mask = _vtoc_bitmap_offset(*cat_loc)
    if not (out[vtoc_off] & mask):
        raise RuntimeError("R31 catalog sector unexpectedly not VTOC-free")
    out[vtoc_off] &= (~mask) & 0xFF
    cat_off = _sector_offset(*cat_loc)
    out[cat_off:cat_off + SECTOR_SIZE] = bytes(SECTOR_SIZE)

    result = bytes(out)
    new_chain = _catalog_sectors(result)
    if new_chain != chain + [cat_loc]:
        raise RuntimeError(
            "R31 catalog extension chain mismatch: "
            f"expected {chain + [cat_loc]}, got {new_chain}"
        )
    print(
        "  R31 catalog extension: PASS "
        f"T{last_trk:02d}/S{last_sec:02d} -> "
        f"T{cat_loc[0]:02d}/S{cat_loc[1]:02d}"
    )
    return result


def _allocate_sector(img: bytes) -> tuple[bytes, tuple[int, int]]:
    """Allocate and clear one DOS 3.3 sector, updating only the VTOC bitmap."""
    trk, sec = _find_free_sector(img)
    out = bytearray(img)
    vtoc_off, mask = _vtoc_bitmap_offset(trk, sec)
    if not (out[vtoc_off] & mask):
        raise RuntimeError(f"sector {trk}/{sec} is not free in VTOC")
    out[vtoc_off] &= (~mask) & 0xFF
    start = _sector_offset(trk, sec)
    out[start:start + SECTOR_SIZE] = bytes(SECTOR_SIZE)
    return bytes(out), (trk, sec)


def _find_free_catalog_slot(img: bytes) -> int:
    vtoc = sector(img, 17, 0)
    trk, sec = vtoc[1], vtoc[2]
    seen: set[tuple[int, int]] = set()
    while trk:
        key = (trk, sec)
        if key in seen:
            raise RuntimeError("catalog T/S loop while finding free slot")
        seen.add(key)
        cat = sector(img, trk, sec)
        next_trk, next_sec = cat[1], cat[2]
        base = _sector_offset(trk, sec)
        for off in range(0x0B, 0x100 - 34, 35):
            if cat[off] in (0x00, 0xFF):
                return base + off
        trk, sec = next_trk, next_sec
    raise RuntimeError("DOS catalog has no free entry for R31 overlay")


def _encode_dos_name(name: str) -> bytes:
    raw = name.upper().encode("ascii")
    if not 1 <= len(raw) <= 30:
        raise ValueError("DOS filename must be 1..30 ASCII characters")
    if any(c in b",= ;" for c in raw):
        raise ValueError(f"unsupported DOS filename {name!r}")
    return bytes(c | 0x80 for c in raw) + bytes([0xA0]) * (30 - len(raw))


def add_dos_binary(
    img: bytes,
    name: str,
    payload: bytes,
    *,
    load: int,
    template_name: str,
) -> bytes:
    """Create a new one-T/S-list DOS 3.3 binary file."""
    if any(e["name"].upper() == name.upper() for e in catalog(img)):
        raise RuntimeError(f"{name}: file already exists")

    packed = (
        load.to_bytes(2, "little")
        + len(payload).to_bytes(2, "little")
        + payload
    )
    data_count = (len(packed) + SECTOR_SIZE - 1) // SECTOR_SIZE
    if data_count > (SECTOR_SIZE - 0x0C) // 2:
        raise RuntimeError(f"{name}: payload needs multiple T/S-list sectors")

    slot = _find_free_catalog_slot(img)
    template = find_entry(img, template_name)

    out, ts_loc = _allocate_sector(img)
    data_locs: list[tuple[int, int]] = []
    for _ in range(data_count):
        out, loc = _allocate_sector(out)
        data_locs.append(loc)

    outb = bytearray(out)
    ts_start = _sector_offset(*ts_loc)
    # First/only T/S list: next pointer and sector offset are already zero.
    for index, (trk, sec) in enumerate(data_locs):
        off = ts_start + 0x0C + index * 2
        outb[off] = trk
        outb[off + 1] = sec

    padded = packed + bytes(data_count * SECTOR_SIZE - len(packed))
    for index, (trk, sec) in enumerate(data_locs):
        start = _sector_offset(trk, sec)
        chunk = padded[index * SECTOR_SIZE:(index + 1) * SECTOR_SIZE]
        outb[start:start + SECTOR_SIZE] = chunk

    entry = bytearray(35)
    entry[0], entry[1] = ts_loc
    entry[2] = template["type"] | (0x80 if template["locked"] else 0)
    entry[3:33] = _encode_dos_name(name)
    sectors_used = 1 + data_count
    entry[33] = sectors_used & 0xFF
    entry[34] = (sectors_used >> 8) & 0xFF
    outb[slot:slot + 35] = entry

    result = bytes(outb)
    check_load, check_payload = read_dos_binary(result, name)
    if check_load != load or check_payload != payload:
        raise RuntimeError(f"{name}: new DOS binary failed read-back")
    print(
        f"  added {name}: load=0x{load:04X} len={len(payload)} "
        f"T/S=T{ts_loc[0]:02d}/S{ts_loc[1]:02d} "
        f"data_sectors={data_count} sha256={sha256(payload)}"
    )
    return result


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


R29_HELPER_BYTES = bytes.fromhex(
    "F0 02 A2 01 CA 4C 03 18"
)

R30_DRAW4_SHA256 = (
    "4360a87c4663b50aad99c6a5f7fca75"
    "f997d3b23ff8e73bd3f783619f9d03235"
)
R30_IMAGE_SHA256 = None  # R31 staging: repin after all type-10 splits

R30_STRSUB_OLD = bytes.fromhex(
    "46 5D B0 01 60 A6 5F CA 8A 0A 85 5E"
)


def _signed8(value: int) -> int:
    return value - 256 if value & 0x80 else value


def _branch_target(instruction_offset: int, operand: int) -> int:
    return instruction_offset + 2 + _signed8(operand)


def _find_r30_strsend(
    payload: bytes,
    *,
    before_offset: int | None = None,
) -> tuple[int, int, int]:
    """Locate and validate the historical STRSEND color wrapper.

    Returns (start, end, STRSUB absolute address). The parser accepts either
    zero-page or absolute LDX FCOLOR, but validates all three historical
    branches against their semantic labels before accepting the block.
    """
    prefix = bytes.fromhex("84 5B A9 01 85 5D AD F8 95")
    hits = []

    for start in range(len(payload)):
        if not payload.startswith(prefix, start):
            continue
        p = start + len(prefix)

        if p + 2 > len(payload) or payload[p] != 0xF0:
            continue
        beq_send2 = p
        p += 2

        if p >= len(payload):
            continue
        if payload[p] == 0xA6:
            p += 2
        elif payload[p] == 0xAE:
            p += 3
        else:
            continue

        if p + 3 > len(payload) or payload[p] != 0xBD:
            continue
        p += 3

        if not payload.startswith(bytes.fromhex("85 5D A9 03"), p):
            continue
        p += 4

        send2 = p
        if not payload.startswith(bytes.fromhex("85 5F"), p):
            continue
        p += 2

        if p + 2 > len(payload) or payload[p] != 0xF0:
            continue
        beq_send4 = p
        p += 2

        send3 = p
        if not payload.startswith(bytes.fromhex("A6 5F"), p):
            continue
        p += 2

        if p + 3 > len(payload) or payload[p] != 0x20:
            continue
        p += 3  # COLORCHG

        send4 = p
        if p + 3 > len(payload) or payload[p] != 0x20:
            continue
        strsub_addr = payload[p + 1] | (payload[p + 2] << 8)
        p += 3

        if not payload.startswith(bytes.fromhex("C6 5F"), p):
            continue
        p += 2

        if p + 2 > len(payload) or payload[p] != 0x10:
            continue
        bpl_send3 = p
        p += 2
        end = p

        if _branch_target(
            beq_send2, payload[beq_send2 + 1]
        ) != send2:
            continue
        if _branch_target(
            beq_send4, payload[beq_send4 + 1]
        ) != send4:
            continue
        if _branch_target(
            bpl_send3, payload[bpl_send3 + 1]
        ) != send3:
            continue

        if before_offset is None or start < before_offset:
            hits.append((start, end, strsub_addr))

    if len(hits) != 1:
        raise RuntimeError(
            "DRAW4: expected one historical text STRSEND wrapper"
            + (
                f" before +0x{before_offset:04X}"
                if before_offset is not None
                else ""
            )
            + f", found {len(hits)}"
        )
    return hits[0]


def _find_unique_bytes(
    payload: bytes,
    needle: bytes,
    what: str,
) -> int:
    hits = [
        i for i in range(len(payload))
        if payload.startswith(needle, i)
    ]
    if len(hits) != 1:
        raise RuntimeError(
            f"DRAW4: expected one {what}, found {len(hits)}"
        )
    return hits[0]


R31_GCDRAW_SHA256 = (
    "be8bbee04098717019870a60b5f16f00"
    "2427412e7399cadbcc179d7c0f7d34a7"
)
R31_MENUS3_SHA256 = (
    "7b5ae3c771f69c20235a7914cb8bc271"
    "5e5e1b23c0c8775549a9cfe145030814"
)
R31_MENUS4_SHA256 = (
    "583764b31d2c27827fbd33abe075d77e"
    "3436d495df7f1d8c5955ed40640adc6e"
)
R31_LHDRAW_ORIG_HEAD_SHA256 = (
    "16d6264b3a6f815f4138677967b235b3"
    "7582713ec5bcc2c23f39cbeb3082282f"
)
R31_LHDRAW_OKI_HEAD_SHA256 = (
    "ee5dcf9ef4173dcc6afb8a118f95f451"
    "cca4c4861888c536b7323afeb15e8b59"
)
R31_LHDRAW_HEAD_LENGTH = 1791


def patch_menus3_stationery_wrapper(
    img: bytes,
) -> tuple[bytes, bytes]:
    """Patch only MENUS3's BLOAD JSR target; append wrapper in EOF slack."""
    load, payload = read_dos_binary(img, "MENUS3")
    expect = EXPECTED_ORIGINAL["MENUS3"]
    if load != expect["load"] or len(payload) != expect["length"]:
        raise RuntimeError("MENUS3: unexpected historical runtime shape")
    if sha256(payload) != expect["sha256"]:
        raise RuntimeError("MENUS3: historical runtime hash mismatch")

    name = b"DRAW3,D1"
    name_hits = [
        i for i in range(len(payload))
        if payload.startswith(name, i)
    ]
    if len(name_hits) != 1:
        raise RuntimeError(
            f"MENUS3: expected one DRAW3,D1 string, found {len(name_hits)}"
        )
    name_addr = load + name_hits[0]

    # Locate the unique LDX #<DRAW3 ; LDY #>DRAW3 ; JSR BLOAD sequence.
    seq = bytes([
        0xA2, name_addr & 0xFF,
        0xA0, name_addr >> 8,
        0x20, 0x09, 0x08,
    ])
    hits = [
        i for i in range(len(payload) - len(seq) + 1)
        if payload[i:i + len(seq)] == seq
    ]
    if len(hits) != 1:
        raise RuntimeError(
            f"MENUS3: expected one DRAW3 BLOAD sequence, found {len(hits)}"
        )
    seq_off = hits[0]
    jsr_off = seq_off + 4
    if payload[jsr_off:jsr_off + 3] != bytes([0x20, 0x09, 0x08]):
        raise RuntimeError("MENUS3: BLOAD call bytes changed")

    wrapper_addr = load + len(payload)
    wrapper = bytes([
        0x20, 0x09, 0x08,             # JSR BLOAD
        0xD0, 0x13,                   # BNE fail/RTS
        0xAD, 0xF1, 0x95,             # LDA $95F1 / PRTYPE
        0xC9, 0x0A,                   # CMP #10
        0xD0, 0x0C,                   # BNE success
        0xA9, 0x00,                   # LDA #0
        0x8D, 0xE5, 0x7E,             # STA $7EE5
        0xA9, 0x44,                   # LDA #$44
        0x8D, 0xE7, 0x7E,             # STA $7EE7
        0xA9, 0x00,                   # success: LDA #0 => Z=1
        0x60,                         # fail/success: RTS
    ])
    if len(wrapper) != 25:
        raise AssertionError("MENUS3 stationery wrapper must remain 25 bytes")

    entry = find_entry(img, "MENUS3")
    capacity = len(file_sector_locations(img, entry)) * SECTOR_SIZE - 4
    if len(payload) + len(wrapper) > capacity:
        raise RuntimeError(
            f"MENUS3: wrapper exceeds capacity {capacity}"
        )

    patched = bytearray(payload)
    patched[jsr_off + 1] = wrapper_addr & 0xFF
    patched[jsr_off + 2] = wrapper_addr >> 8
    patched += wrapper

    # Existing code is unchanged except the two-byte JSR operand.
    changed = [
        i for i, (a, b) in enumerate(zip(payload, patched[:len(payload)]))
        if a != b
    ]
    if changed != [jsr_off + 1, jsr_off + 2]:
        raise RuntimeError(
            f"MENUS3: unexpected in-body changes {changed}"
        )

    out = rewrite_dos_binary(img, "MENUS3", bytes(patched))
    check_load, check = read_dos_binary(out, "MENUS3")
    if check_load != load or check != bytes(patched):
        raise RuntimeError("MENUS3: wrapper read-back failed")
    print(
        "  patched MENUS3 stationery wrapper: PASS "
        f"BLOAD JSR +0x{jsr_off:04X} -> 0x{wrapper_addr:04X}; "
        f"RAM patches $7EE5/$7EE7; len={len(patched)}/{capacity}"
    )
    return out, bytes(patched)


def patch_draw1_dispatch(img: bytes) -> tuple[bytes, bytes]:
    """Use DRAW1 EOF slack to tail-load DRAW6 only for printer type 10.

    Non-type-10 execution pays only the dispatcher and then jumps to the
    exact historical DRAW1 entry target.  Type 10 reuses MENUS1's existing
    DRAW1,D1 filename buffer, changes only its digit to 6, and manually
    supplies BLOAD's return address as $77FF so RTS lands at $7800 after
    DRAW6 has overwritten the dispatcher itself.
    """
    load, payload = read_dos_binary(img, "DRAW1")
    if load != 0x7800 or len(payload) != 2737:
        raise RuntimeError("DRAW1: unexpected historical runtime shape")
    if payload[0] != 0x4C:
        raise RuntimeError("DRAW1: historical entry is not JMP absolute")
    old_target = payload[1] | (payload[2] << 8)
    if not (load <= old_target < load + len(payload)):
        raise RuntimeError(
            f"DRAW1: historical entry target 0x{old_target:04X} is outside file"
        )

    menu_load, menu = read_dos_binary(img, "MENUS1")
    if menu_load != 0x4000:
        raise RuntimeError("MENUS1: unexpected load address")
    needle = b"DRAW1,D1"
    hits = [
        i for i in range(len(menu))
        if menu.startswith(needle, i)
    ]
    if len(hits) != 1:
        raise RuntimeError(
            f"MENUS1: expected one DRAW1,D1 filename, found {len(hits)}"
        )
    filename_addr = menu_load + hits[0]
    digit_addr = filename_addr + 4

    stub_addr = load + len(payload)
    stub = bytes([
        0xAD, 0xF1, 0x95,             # LDA $95F1 / PRTYPE
        0xC9, 0x0A,                   # CMP #10
        0xF0, 0x03,                   # BEQ type10
        0x4C, old_target & 0xFF, old_target >> 8,
        0xA9, 0x36,                   # type10: LDA #'6'
        0x8D, digit_addr & 0xFF, digit_addr >> 8,
        0xA2, filename_addr & 0xFF,   # LDX #<DRAW1 filename
        0xA0, filename_addr >> 8,     # LDY #>DRAW1 filename
        0xA9, 0x77,                   # synthetic RTS target $77FF
        0x48,
        0xA9, 0xFF,
        0x48,
        0x4C, 0x09, 0x08,             # JMP BLOAD
    ])
    if len(stub) != 28:
        raise AssertionError("R31 DRAW1 dispatcher must remain 28 bytes")

    entry = find_entry(img, "DRAW1")
    capacity = len(file_sector_locations(img, entry)) * SECTOR_SIZE - 4
    if len(payload) + len(stub) > capacity:
        raise RuntimeError(
            f"DRAW1: dispatcher exceeds existing payload capacity {capacity}"
        )
    if load + len(payload) + len(stub) > DRAW_OVERLAY_LIMIT:
        raise RuntimeError("DRAW1: dispatcher would cross $8300 overlay limit")

    patched = bytearray(payload)
    patched[0:3] = bytes([
        0x4C, stub_addr & 0xFF, stub_addr >> 8
    ])
    patched += stub

    if patched[3:len(payload)] != payload[3:]:
        raise RuntimeError("DRAW1: historical body changed outside entry JMP")
    if patched[len(payload):] != stub:
        raise RuntimeError("DRAW1: dispatcher append mismatch")

    out = rewrite_dos_binary(img, "DRAW1", bytes(patched))
    check_load, check = read_dos_binary(out, "DRAW1")
    if check_load != load or check != bytes(patched):
        raise RuntimeError("DRAW1: dispatcher read-back failed")

    print(
        "  patched DRAW1 dispatcher: PASS "
        f"old_entry=0x{old_target:04X} stub=0x{stub_addr:04X} "
        f"MENUS1 filename=0x{filename_addr:04X} "
        f"len={len(patched)}/{capacity}"
    )
    return out, bytes(patched)


def build_stationery_draw7_payload(
    img: bytes,
    patched_head: bytes,
) -> bytes:
    """Rebuild DRAW7 as patched 1791-byte LHDRAW head + shipped tail."""
    load, shipped = read_dos_binary(img, "DRAW3")
    if load != 0x7800 or len(shipped) != 2811:
        raise RuntimeError("DRAW3: unexpected shipped stationery overlay")
    head = shipped[:R31_LHDRAW_HEAD_LENGTH]
    if sha256(head) != R31_LHDRAW_ORIG_HEAD_SHA256:
        raise RuntimeError(
            "DRAW3: shipped prefix does not match historical LHDRAW source"
        )
    if len(patched_head) != R31_LHDRAW_HEAD_LENGTH:
        raise RuntimeError(
            f"LHDRAW.OKI: expected {R31_LHDRAW_HEAD_LENGTH} bytes, "
            f"got {len(patched_head)}"
        )
    if sha256(patched_head) != R31_LHDRAW_OKI_HEAD_SHA256:
        raise RuntimeError("LHDRAW.OKI: deterministic head hash mismatch")

    diffs = [
        (i, old, new)
        for i, (old, new) in enumerate(zip(head, patched_head))
        if old != new
    ]
    if len(diffs) != 2:
        raise RuntimeError(
            f"LHDRAW.OKI: expected two immediate-byte changes, got {len(diffs)}"
        )
    transitions = [(old, new) for _, old, new in diffs]
    if transitions != [(40, 0), (14, 68)]:
        raise RuntimeError(
            "LHDRAW.OKI: expected only X=40->0 and Y=14->68; "
            f"got {transitions}"
        )

    result = patched_head + shipped[R31_LHDRAW_HEAD_LENGTH:]
    if len(result) != len(shipped):
        raise RuntimeError("DRAW7: reconstruction changed runtime length")
    print(
        "  reconstructed DRAW7 stationery: PASS "
        f"head={len(patched_head)} tail={len(shipped)-len(patched_head)} "
        f"sha256={sha256(result)}"
    )
    return result


def build_banner_draw8_payload(img: bytes) -> bytes:
    """Build the hardware-golden R30 banner as a separate DRAW8 payload."""
    load, payload = read_dos_binary(img, "DRAW4")
    expect = EXPECTED_ORIGINAL["DRAW4"]
    if load != expect["load"]:
        raise RuntimeError("DRAW4: unexpected load address")
    if len(payload) != expect["length"] or sha256(payload) != expect["sha256"]:
        raise RuntimeError("DRAW4: shipped banner overlay mismatch")
    patched, _ = patch_banner_draw4_payload(payload, load)
    if sha256(patched) != R30_DRAW4_SHA256:
        raise RuntimeError("DRAW8: R30 banner hash mismatch")
    return patched


def _build_r30_strsend(
    *,
    strsub_addr: int,
    feed_helper_addr: int,
    block_len: int,
) -> bytes:
    """Build the in-place R30 true-row densifier.

    Schedule:
      - send every nonblank source row once;
      - duplicate BITCNT 8 and 5 in every group;
      - duplicate BITCNT 2 except when (SADDR & 3) == 2.

    Across four complete 8-row groups this schedules 11 duplicates:
    32 source rows -> 43 physical rows, versus the exact 42 2/3-row target.
    """
    out = bytearray()
    branches: list[tuple[int, str]] = []
    labels: dict[str, int] = {}

    def emit(*values: int) -> None:
        out.extend(values)

    def branch(opcode: int, label: str) -> None:
        emit(opcode, 0)
        branches.append((len(out) - 1, label))

    emit(0x84, 0x5B)  # STY FNZY
    emit(0x20, strsub_addr & 0xFF, strsub_addr >> 8)
    emit(0xA5, 0x58)  # LDA BITCNT
    emit(0xC9, 0x08)
    branch(0xF0, "dup")
    emit(0xC9, 0x05)
    branch(0xF0, "dup")
    emit(0xC9, 0x02)
    branch(0xD0, "done")
    emit(0xA5, 0x52)  # LDA SADDR
    emit(0x29, 0x03)
    emit(0xC9, 0x02)
    branch(0xF0, "done")

    labels["dup"] = len(out)
    emit(0xA0, 0x01)  # LDY #1
    emit(
        0x20,
        feed_helper_addr & 0xFF,
        feed_helper_addr >> 8,
    )
    emit(0x20, strsub_addr & 0xFF, strsub_addr >> 8)

    if len(out) > block_len:
        raise RuntimeError(
            f"DRAW4: R30 STRSEND needs {len(out)} bytes but "
            f"historical block has only {block_len}"
        )
    out.extend([0xEA] * (block_len - len(out)))
    labels["done"] = len(out)

    for operand_index, label in branches:
        target = labels[label]
        next_pc = operand_index + 1
        delta = target - next_pc
        if not -128 <= delta <= 127:
            raise RuntimeError(
                f"DRAW4: R30 branch to {label} is out of range"
            )
        out[operand_index] = delta & 0xFF

    return bytes(out)


def patch_banner_draw4_payload(
    payload: bytes,
    load: int = 0x7800,
) -> tuple[bytes, dict[str, int]]:
    """R30: true banner-text row replay plus frozen R29 icon geometry.

    The exact shipped 1012-byte DRAW4 remains the address basis. Existing
    routines are patched length-for-length; the only payload growth remains
    the already-proven eight-byte R29 icon helper in EOF slack.
    """
    text_off = _find_unique_bytes(
        payload,
        BANNER_TEXT_CALL,
        "BSTR6 native-feed site",
    )
    icon_off = _find_unique_bytes(
        payload,
        BANNER_ICON_CALL,
        "BICON2 spacing site",
    )
    strsend_off, strsend_end, strsub_addr = _find_r30_strsend(
        payload,
        before_offset=icon_off,
    )
    strsub_off = strsub_addr - load
    if not (
        0 <= strsub_off
        <= len(payload) - len(R30_STRSUB_OLD)
    ):
        raise RuntimeError(
            f"DRAW4: STRSEND points outside DRAW4 to STRSUB "
            f"0x{strsub_addr:04X}"
        )
    found_strsub = payload[
        strsub_off:strsub_off + len(R30_STRSUB_OLD)
    ]
    if found_strsub != R30_STRSUB_OLD:
        raise RuntimeError(
            "DRAW4: STRSEND target does not contain the historical "
            f"STRSUB prologue at +0x{strsub_off:04X}; "
            f"found {found_strsub.hex(' ')}"
        )

    if text_off != 0x0085:
        raise RuntimeError(
            f"DRAW4: BSTR6 moved from +0x0085 to +0x{text_off:04X}"
        )
    if icon_off != 0x02BE:
        raise RuntimeError(
            f"DRAW4: BICON2 moved from +0x02BE to +0x{icon_off:04X}"
        )
    bstr9_addr = load + strsub_off + len(R30_STRSUB_OLD)
    feed_helper_addr = load + strsub_off + 7

    helper_addr = load + len(payload)
    if helper_addr != 0x7BF4:
        raise RuntimeError(
            f"DRAW4: expected R29 icon helper at $7BF4, "
            f"got 0x{helper_addr:04X}"
        )

    patched = bytearray(payload)

    # BSTR6 intentionally remains the historical X=0,Y=1,JSR CRLF.
    # Once graphics is active, frozen R27 PRCOMS turns that into one native
    # $03,$0E feed; no synthetic X spacing remains in R30.
    if patched[
        text_off:text_off + len(BANNER_TEXT_CALL)
    ] != BANNER_TEXT_CALL:
        raise RuntimeError("DRAW4: BSTR6 native-feed bytes changed unexpectedly")

    # Preserve the hardware-good R29 icon patch byte-for-byte.
    icon_new = bytes([
        0xA2, 0x03,             # LDX #3
        0xA0, 0x01,             # LDY #1
        0xA5, 0x54,             # LDA XCUR
        0x29, 0x07,             # AND #7
        0x20,                   # JSR $7BF4
        helper_addr & 0xFF,
        (helper_addr >> 8) & 0xFF,
    ])
    if len(icon_new) != len(BANNER_ICON_CALL):
        raise AssertionError("R30 icon patch must remain length-preserving")
    patched[icon_off:icon_off + len(icon_new)] = icon_new

    # Monomorphize STRSUB to the exact historical monochrome setup:
    # COLOR=0 originally computes RBTEMP=$FE. The normal entry jumps directly
    # to BSTR9. Its five now-unreachable bytes become a tiny native-feed
    # helper used only by the duplicate scheduler.
    strsub_new = bytes([
        0xA9, 0xFE,             # LDA #$FE
        0x85, 0x5E,             # STA RBTEMP
        0x4C,                   # JMP BSTR9
        bstr9_addr & 0xFF,
        (bstr9_addr >> 8) & 0xFF,
        0xA2, 0x00,             # helper: LDX #0
        0x4C, 0x03, 0x18,       # JMP CRLF; caller supplies Y=1
    ])
    if len(strsub_new) != len(R30_STRSUB_OLD):
        raise AssertionError("R30 STRSUB replacement must be 12 bytes")
    patched[
        strsub_off:strsub_off + len(strsub_new)
    ] = strsub_new

    strsend_len = strsend_end - strsend_off
    strsend_new = _build_r30_strsend(
        strsub_addr=strsub_addr,
        feed_helper_addr=feed_helper_addr,
        block_len=strsend_len,
    )
    patched[strsend_off:strsend_end] = strsend_new

    # Append exactly the hardware-good R29 icon helper. R30 text never enters
    # it; this makes the icon path byte-for-byte identical to R29.
    patched += R29_HELPER_BYTES

    if len(patched) != 1020:
        raise RuntimeError(
            f"DRAW4: R30 must be exactly 1020 bytes, got {len(patched)}"
        )
    if load + len(patched) != 0x7BFC:
        raise RuntimeError(
            f"DRAW4: unexpected R30 end 0x{load + len(patched):04X}"
        )
    if patched[1012:] != R29_HELPER_BYTES:
        raise RuntimeError("DRAW4: R29 icon helper changed in R30")

    allowed = set(range(icon_off, icon_off + len(icon_new)))
    allowed.update(range(strsub_off, strsub_off + len(strsub_new)))
    allowed.update(range(strsend_off, strsend_end))
    changed = {
        i
        for i, (old, new) in enumerate(
            zip(payload, patched[:len(payload)])
        )
        if old != new
    }
    if not changed.issubset(allowed):
        unexpected = sorted(changed - allowed)
        raise RuntimeError(
            "DRAW4: bytes changed outside R30 fixed patch regions: "
            + ", ".join(f"+0x{i:04X}" for i in unexpected)
        )

    return bytes(patched), {
        "text_site": text_off,
        "icon_site": icon_off,
        "strsend_site": strsend_off,
        "strsend_len": strsend_len,
        "strsub_site": strsub_off,
        "strsub_addr": strsub_addr,
        "feed_helper": feed_helper_addr,
        "icon_helper": helper_addr,
    }


def patch_banner_draw4(img: bytes) -> tuple[bytes, bytes]:
    load, payload = read_dos_binary(img, "DRAW4")
    expect = EXPECTED_ORIGINAL["DRAW4"]
    if load != expect["load"]:
        raise RuntimeError("DRAW4: unexpected load address")
    if len(payload) != expect["length"] or sha256(payload) != expect["sha256"]:
        raise RuntimeError(
            "DRAW4: runtime base does not match known 1012-byte image"
        )

    patched_payload, info = patch_banner_draw4_payload(payload, load)
    patched_hash = sha256(patched_payload)
    if patched_hash != R30_DRAW4_SHA256:
        raise RuntimeError(
            "DRAW4: R30 deterministic hash mismatch; expected "
            f"{R30_DRAW4_SHA256}, got {patched_hash}"
        )

    # 4-byte DOS binary header + 1020-byte payload = exactly four sectors.
    entry = find_entry(img, "DRAW4")
    capacity = len(file_sector_locations(img, entry)) * SECTOR_SIZE
    packed_length = 4 + len(patched_payload)
    if capacity != 1024 or packed_length != capacity:
        raise RuntimeError(
            f"DRAW4: expected exact 1024-byte allocation fit; "
            f"packed={packed_length} capacity={capacity}"
        )

    out = rewrite_dos_binary(
        img,
        "DRAW4",
        patched_payload,
        allow_expand=False,
    )
    check_load, check_payload = read_dos_binary(out, "DRAW4")
    if check_load != load or check_payload != patched_payload:
        raise RuntimeError("DRAW4: R30 patch read-back failed")

    print(
        "  patched runtime DRAW4 in-place: PASS "
        f"BSTR6 native +0x{info['text_site']:04X}; "
        f"STRSEND +0x{info['strsend_site']:04X} "
        f"len={info['strsend_len']}; "
        f"STRSUB +0x{info['strsub_site']:04X}; "
        f"icon +0x{info['icon_site']:04X} -> "
        f"helper 0x{info['icon_helper']:04X}"
    )
    print(
        "  address/state contract: PASS "
        "BITCNT=$58, SADDR=$52, XCUR=$54; "
        f"row-feed helper=0x{info['feed_helper']:04X}; "
        "R29 icon helper=$7BF4-$7BFB; no existing address moved"
    )
    print(
        f"  R30 DRAW4 len={len(patched_payload)} "
        f"RAM=0x{load:04X}-0x{load + len(patched_payload) - 1:04X} "
        f"packed={packed_length}/{capacity} "
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
        raise RuntimeError("R30 must not grow resident SYSLIB")

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
    ap.add_argument("--menus4", type=pathlib.Path, required=True)
    ap.add_argument(
        "--gcdraw",
        type=pathlib.Path,
        required=True,
        help="compiled type-10 GCDRAW payload; installed as new DRAW6",
    )
    ap.add_argument("--output", type=pathlib.Path, required=True)
    args = ap.parse_args()

    img = args.base_disk.read_bytes() if args.base_disk else fetch_base()
    if len(img) != EXPECTED_IMAGE_SIZE:
        raise RuntimeError(
            f"base image must be {EXPECTED_IMAGE_SIZE} bytes; got {len(img)}"
        )

    entries = {e["name"].upper(): e for e in catalog(img)}
    required = (
        "PRCOMS", "MENUS7", "MENUS1", "MENUS3", "MENUS4",
        "DRAW1", "DRAW3", "DRAW4", "SYSLIB",
    )
    for name in required:
        if name not in entries:
            raise RuntimeError(f"base disk missing required file {name}")
    for name in ("DRAW6", "DRAW8"):
        if name in entries:
            raise RuntimeError(f"base disk unexpectedly already contains {name}")

    print("Validating exact Print Shop runtime base...")
    verify_original(img)

    _, original_draw3 = read_dos_binary(img, "DRAW3")
    _, original_draw4 = read_dos_binary(img, "DRAW4")

    prcoms = args.prcoms.read_bytes()
    menus7 = args.menus7.read_bytes()
    menus4 = args.menus4.read_bytes()
    gcdraw = args.gcdraw.read_bytes()

    inputs = {
        "PRCOMS": prcoms,
        "MENUS7": menus7,
        "MENUS4": menus4,
        "GCDRAW/DRAW6": gcdraw,
    }
    for name, data in inputs.items():
        print(f"  input {name} len={len(data)} sha256={sha256(data)}")

    expected_inputs = {
        "PRCOMS": (
            2044,
            "e5d235ac23ecfc5b593bd9b46c74bf1669265a1db0b73f9e280df811b31dfa95",
        ),
        "MENUS7": (
            3041,
            "f6177227faff75262e4cac378488e5ec244a956663ed3173d01fb4e72c13fd85",
        ),
        "MENUS4": (1525, R31_MENUS4_SHA256),
        "GCDRAW/DRAW6": (2810, R31_GCDRAW_SHA256),
    }
    for name, (length, digest) in expected_inputs.items():
        data = inputs[name]
        if len(data) != length or sha256(data) != digest:
            raise RuntimeError(
                f"{name}: R31 build input mismatch "
                f"len={len(data)} sha256={sha256(data)}"
            )

    print("Reclaiming proven-stale sectors from untouched base disk...")
    img = reclaim_r31_overlay_sectors(img)
    img = extend_r31_catalog(img)

    print("Installing R31 resident and menu selectors...")
    img = rewrite_dos_binary(img, "PRCOMS", prcoms)
    img = rewrite_dos_binary(img, "MENUS7", menus7)
    img = rewrite_dos_binary(img, "MENUS4", menus4)

    print("Installing R31 stationery wrapper without moving MENUS3 code...")
    img, menus3 = patch_menus3_stationery_wrapper(img)

    print("Installing R31 cards/signs dispatch without growing MENUS1...")
    img, draw1 = patch_draw1_dispatch(img)

    print("Adding type-10 OkiGraph alternate overlays...")
    img = add_dos_binary(
        img, "DRAW6", gcdraw, load=0x7800, template_name="DRAW1"
    )
    draw8 = build_banner_draw8_payload(img)
    img = add_dos_binary(
        img, "DRAW8", draw8, load=0x7800, template_name="DRAW4"
    )

    # The 17-sector reclaim pool must be consumed exactly: no new free-space
    # side effect and no allocator drift into unrelated sectors.
    pool = set(R31_OVERLAY_SECTORS)
    if _vtoc_sector_is_free(img, *R31_CATALOG_SECTOR):
        raise RuntimeError("R31 catalog sector became free after extension")
    if R31_CATALOG_SECTOR not in set(_catalog_sectors(img)):
        raise RuntimeError("R31 catalog sector is not in live catalog chain")

    draw6_entry = find_entry(img, "DRAW6")
    draw8_entry = find_entry(img, "DRAW8")
    consumed = set(_ts_list_sectors(img, draw6_entry))
    consumed.update(file_sector_locations(img, draw6_entry))
    consumed.update(_ts_list_sectors(img, draw8_entry))
    consumed.update(file_sector_locations(img, draw8_entry))
    if consumed != pool:
        raise RuntimeError(
            "R31 overlay allocation escaped deterministic reclaim pool: "
            f"expected {sorted(pool)}, got {sorted(consumed)}"
        )
    still_free = [
        loc for loc in sorted(pool)
        if _vtoc_sector_is_free(img, *loc)
    ]
    if still_free:
        raise RuntimeError(
            f"R31 reclaim left pool sectors free: {still_free}"
        )
    print(
        "  R31 overlay allocation contract: PASS "
        "DRAW6 + DRAW8 consume all 17 overlay sectors exactly; "
        "T32/S09 remains the live added catalog sector"
    )

    print("Applying R14 paper-position patch without growing SYSLIB...")
    img, syslib = patch_test_paper_cr_only(img)

    # DRAW3 and DRAW4 must remain byte-for-byte historical for stock printers.
    _, check_draw3 = read_dos_binary(img, "DRAW3")
    _, check_draw4 = read_dos_binary(img, "DRAW4")
    if check_draw3 != original_draw3:
        raise RuntimeError("R31 changed historical DRAW3")
    if check_draw4 != original_draw4:
        raise RuntimeError("R31 changed historical DRAW4")
    print(
        "  legacy overlay preservation: PASS "
        "DRAW3 and DRAW4 remain byte-for-byte historical"
    )

    print("Reading R31 files back through DOS T/S chains...")
    verify_patched(
        img,
        {
            "PRCOMS": prcoms,
            "MENUS7": menus7,
            "MENUS3": menus3,
            "MENUS4": menus4,
            "DRAW1": draw1,
            "DRAW6": gcdraw,
            "DRAW8": draw8,
            "SYSLIB": syslib,
        },
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(img)

    digest = sha256(img)
    if (
        R30_IMAGE_SHA256 is not None
        and digest != R30_IMAGE_SHA256
    ):
        raise RuntimeError(
            "runtime image hash mismatch; expected "
            f"{R30_IMAGE_SHA256}, got {digest}"
        )
    print(f"Runtime image: {args.output}")
    print(f"Image bytes: {len(img)}")
    print(f"Image SHA256: {digest}")
    print(
        "PASS: R31 separate stock 92/93 and type-10 OkiGraph "
        "runtime disk constructed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
