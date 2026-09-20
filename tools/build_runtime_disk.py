#!/usr/bin/env python3
"""Build a runnable Print Shop OkiGraph I runtime disk.

The base image is the DOS 3.4 Color Print Shop runtime whose PRCOMS,
MENUS7, and DRAW1 (GCDRAW.S) binaries exactly match the 1987-01-26 source
snapshot when assembled with Merlin32.

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
    for required in ("PRCOMS", "MENUS7", "DRAW1"):
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

    print("Reading patched overlays back through DOS T/S chains...")
    verify_patched(
        img,
        {"PRCOMS": prcoms, "MENUS7": menus7, "DRAW1": gcdraw},
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
