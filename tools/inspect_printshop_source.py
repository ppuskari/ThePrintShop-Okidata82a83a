#!/usr/bin/env python3
"""Inspect the historical Apple II Print Shop v2 source disks.

Downloads the three 1987-01-26 DOS 3.3 disk images from the Asimov mirror,
lists their catalogs, and emits small context snippets around printer-related
terms. It deliberately does not copy the original source into this repo.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import urllib.parse
import urllib.request

BASE = (
    "https://mirrors.apple2.org.za/ftp.apple.asimov.net/"
    "images/productivity/graphics/printshop/"
)
NAMES = [
    "The Print Shop V2.0 source code 1987-01-26 disk 1 of 3.dsk",
    "The Print Shop V2.0 source code 1987-01-26 disk 2 of 3.dsk",
    "The Print Shop V2.0 source code 1987-01-26 disk 3 of 3.dsk",
]

TRACKS = 35
SECTORS = 16
SECTOR_SIZE = 256
IMAGE_SIZE = TRACKS * SECTORS * SECTOR_SIZE

TERMS = re.compile(
    r"(printer|print[.]|imagewriter|epson|okidata|okig|microline|driver|graphics|raster|"
    r"bit.?image|parallel|serial|interface|pr#|sendgc|gcout|sendrow|lfcr|line.feed|"\n    r"prparams|crlf|sgc[0-9a-z]*|gc[0-9][a-z]*|okidata|okig)",
    re.IGNORECASE,
)


def sector(img: bytes, track: int, sec: int) -> bytes:
    if not (0 <= track < TRACKS and 0 <= sec < SECTORS):
        raise ValueError(f"invalid T/S {track}/{sec}")
    p = (track * SECTORS + sec) * SECTOR_SIZE
    return img[p:p + SECTOR_SIZE]


def dos_name(raw: bytes) -> str:
    return bytes(b & 0x7F for b in raw).decode("ascii", "replace").rstrip()


def catalog(img: bytes):
    vtoc = sector(img, 17, 0)
    trk, sec = vtoc[1], vtoc[2]
    seen = set()
    while trk:
        if (trk, sec) in seen:
            raise ValueError("catalog T/S loop")
        seen.add((trk, sec))
        cat = sector(img, trk, sec)
        next_trk, next_sec = cat[1], cat[2]
        for off in range(0x0B, 0x100 - 34, 35):
            ent = cat[off:off + 35]
            ts_trk = ent[0]
            if ts_trk in (0x00, 0xFF):
                continue
            ts_sec = ent[1]
            ftype = ent[2] & 0x7F
            locked = bool(ent[2] & 0x80)
            name = dos_name(ent[3:33])
            sectors_used = ent[33] | (ent[34] << 8)
            yield {
                "name": name,
                "type": ftype,
                "locked": locked,
                "sectors": sectors_used,
                "ts_track": ts_trk,
                "ts_sector": ts_sec,
            }
        trk, sec = next_trk, next_sec


def file_sectors(img: bytes, entry):
    trk, sec = entry["ts_track"], entry["ts_sector"]
    seen = set()
    chunks = []
    while trk:
        if (trk, sec) in seen:
            raise ValueError(f"T/S-list loop in {entry['name']}")
        seen.add((trk, sec))
        ts = sector(img, trk, sec)
        next_trk, next_sec = ts[1], ts[2]
        for off in range(0x0C, 0x100 - 1, 2):
            dt, ds = ts[off], ts[off + 1]
            if dt == 0:
                continue
            if dt >= TRACKS or ds >= SECTORS:
                continue
            chunks.append(sector(img, dt, ds))
        trk, sec = next_trk, next_sec
    return b"".join(chunks)


def textish(data: bytes) -> str:
    raw = bytes(b & 0x7F for b in data)
    raw = raw.replace(b"\x00", b"\n")
    return raw.decode("ascii", "replace").replace("\r", "\n")


def useful_lines(text: str, context: int = 8, max_hits: int = 100):
    lines = text.splitlines()
    hits = []
    used = set()
    for i, line in enumerate(lines):
        if not TERMS.search(line):
            continue
        lo = max(0, i - context)
        hi = min(len(lines), i + context + 1)
        block = []
        for j in range(lo, hi):
            if j in used:
                continue
            used.add(j)
            clean = lines[j].rstrip()
            if clean:
                block.append((j + 1, clean[:180]))
        if block:
            hits.append(block)
        if len(hits) >= max_hits:
            break
    return hits


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "ThePrintShop-Okidata82a83a-source-scan/1.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if len(data) != IMAGE_SIZE:
        raise ValueError(f"unexpected image size {len(data)} for {url}")
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", type=pathlib.Path)
    ap.add_argument("--report", type=pathlib.Path)
    args = ap.parse_args()

    out = []
    for diskno, name in enumerate(NAMES, 1):
        url = BASE + urllib.parse.quote(name)
        if args.cache_dir:
            args.cache_dir.mkdir(parents=True, exist_ok=True)
            path = args.cache_dir / f"printshop-v2-src-{diskno}.dsk"
            if path.exists() and path.stat().st_size == IMAGE_SIZE:
                img = path.read_bytes()
            else:
                img = fetch(url)
                path.write_bytes(img)
        else:
            img = fetch(url)

        entries = list(catalog(img))
        out.append(f"=== DISK {diskno}: {name} ===")
        out.append(f"Source: {url}")
        out.append("Catalog:")
        for e in entries:
            lock = "*" if e["locked"] else " "
            out.append(
                f" {lock} type=0x{e['type']:02X} sectors={e['sectors']:3d} "
                f"{e['name']}"
            )

        out.append("")
        out.append("Printer-related excerpts:")
        found = 0
        for e in entries:
            try:
                data = file_sectors(img, e)
            except Exception as exc:
                out.append(f"[{e['name']}] extraction error: {exc}")
                continue
            txt = textish(data)
            blocks = useful_lines(txt)
            if not blocks:
                continue
            found += 1
            out.append(f"--- {e['name']} ---")
            for block in blocks:
                for lineno, line in block:
                    out.append(f"{lineno:5d}: {line}")
                out.append("...")
        if not found:
            out.append("(no matching text excerpts)")
        out.append("")

    report = "\n".join(out) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# End of source scanner.
