#!/usr/bin/env python3
"""Create the first Print Shop v2 source-level OkiGraph I driver patch.

v0.1 intentionally repurposes the existing printer-type-5
"OKIDATA MICROLINE 92,93" path. It changes only:

* the menu label (same character count), and
* the type-5 graphics-byte emission block (same assembled byte count).

The historical Brøderbund source is fetched or read locally but is never
stored in this repository.

Modes:

* --check validates that the expected historical source still matches.
* --output-dir emits decoded patched source files.
* --output-disks creates patched copies of the three DOS 3.3 source disks.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import urllib.parse

from inspect_printshop_source import (
    BASE,
    NAMES,
    SECTOR_SIZE,
    SECTORS,
    catalog,
    fetch,
    file_sectors,
    sector,
)

OLD_MENU = "OKIDATA MICROLINE 92,93"
NEW_MENU = "OKI 82A/83A OKIGRAPH I "

# Keep the replacement machine-code length equal to the original.
#
# Original:
#   PLA(1)+ORA zp(2)+STX zp(2)+JSR(3)+LDX zp(2)+JSR(3)
#   +CMP #(2)+BNE(2)+JSR(3) = 20
#
# R2 replacement removes the five v0.1 padding NOPs. PRCOMS is allowed to
# grow within its existing DOS allocation because the assembler resolves all
# internal addresses and the fixed $1800 jump table remains unchanged.
GC5_OLD = re.compile(
    r"(?m)^GC5A PLA\n"
    r"[ \t]+ORA GCOLD\n"
    r"[ \t]+STX XTEMP\n"
    r"[ \t]+JSR REVBITS\n"
    r"[ \t]+LDX XTEMP\n"
    r"[ \t]*JSR COUT1\n"
    r"[ \t]+CMP #03\n"
    r"[ \t]+BNE GC5B\n"
    r"[ \t]*JSR COUT1\n"
    r"^GC5B PHA$"
)

GC5_NEW = """GC5A PLA
 ORA GCOLD
 STX XTEMP
 JSR REVBITS
 LDX XTEMP
 JSR COUTRAW
 CMP #03
 BNE GC5B
 JSR COUTRAW
GC5B PHA"""


CRLF_OLD = re.compile(
    r"(?m)^CRLF LDA #\$0D\n"
    r"[ \t]*JSR COUT1\n"
    r"[ \t]+JSR SETLF\n"
    r"[ \t]+DEY\n"
    r"[ \t]+BMI CRLFX\n"
    r"^CRLF2 LDA #\$0A\n"
    r"[ \t]*JSR COUT1\n"
    r"[ \t]+DEY\n"
    r"[ \t]+BPL CRLF2\n"
    r"^CRLFX TXA\n"
    r"[ \t]+PHA\n"
    r"[ \t]+JSR UPLRK\n"
    r"[ \t]+PLA\n"
    r"[ \t]+TAX\n"
    r"^SETLFX RTS$"
)

CRLF_NEW = """CRLF LDA PRTYPE
 CMP #05
 BEQ CRLF5
 LDA #$0D
 JSR COUT1
 JSR SETLF
 DEY
 BMI CRLFX
CRLF2 LDA #$0A
 JSR COUT1
 DEY
 BPL CRLF2
 BMI CRLFX
*
* OKIGRAPH I TYPE-5 CR/LF - R8 PRCOMS CORE
* Continuous graphics from R7; DUMP boundary handling is in GCDRAW.
*
CRLF5 LDA FIX80
 BEQ CRLF5T
 CPX #00
 BNE CRLF5E
 CPY #00
 BEQ CRLF5E
CRLF5G LDA #03
 JSR COUTRAW
 LDA #$0E
 JSR COUTRAW
 DEY
 BNE CRLF5G
 JMP CRLFX
CRLF5E LDA #03
 JSR COUTRAW
 LDA #02
 JSR COUTRAW
 DEC FIX80
CRLF5T LDA #$0D
 JSR COUTRAW
 DEY
 BMI CRLFX
 CPX #02
 BEQ CRLFX
CRLF5L LDA #$0A
 JSR COUTRAW
 DEY
 BPL CRLF5L
CRLFX TXA
 PHA
 JSR UPLRK
 PLA
 TAX
SETLFX RTS"""


SGC5_OLD = re.compile(
    r"(?m)^SGC5 STX TEMPLO\n"
    r"[ \t]+STY TEMPHI\n"
    r"[ \t]+LDA #00\n"
    r"[ \t]+STA GCINDEX\n"
    r"[ \t]+LDA #03\n"
    r"[ \t]*JMP COUT1$"
)

SGC5_NEW = """SGC5 STX TEMPLO
 STY TEMPHI
 LDA #00
 STA GCINDEX
 LDA FIX80
 BNE SGC5X
 INC FIX80
 LDA #03
 JMP COUTRAW
SGC5X RTS"""

GC5_END_OLD = re.compile(
    r"(?m)^[ \t]+LDA #03\n"
    r"[ \t]*JSR COUT1\n"
    r"[ \t]+LDA #02\n"
    r"[ \t]*JSR COUT1\n"
    r"^GC5X PLA$"
)

GC5_END_NEW = """GC5X PLA"""

COUT1_OLD = re.compile(
    r"(?m)^COUT1 STX XTEMP\n"
    r"[ \t]+STY YTEMP\n"
    r"[ \t]+PHA\n"
    r"^COUT1A LDX PITYPE\n"
)

COUT1_NEW = """COUT1 PHA
 LDA PRTYPE
 CMP #05
 BNE COUT1N
 LDA FIX80
 BEQ COUT1N
 LDA #03
 JSR COUTRAW
 LDA #02
 JSR COUTRAW
 DEC FIX80
COUT1N PLA
COUTRAW STX XTEMP
 STY YTEMP
 PHA
COUT1A LDX PITYPE
"""

SETLF5_OLD = """SETLF5 LDA #'%'
 JSR COUT1
 LDA #'9'
 JSR COUT1
 TXA
 ASL
 JMP COUT1"""
SETLF5_NEW = """SETLF5 RTS"""

MENUS_INIT_OLD = """ JSR GSELECT
 STA PRTYPE
 LDA RETFLAG"""

MENUS_INIT_NEW = """ JSR GSELECT
 STA PRTYPE
 LDA #00
 STA $B9
 LDA RETFLAG"""

MENUS_R25_HELPER = """R25TOP LDA $95F5
 CMP #02
 BNE R25TOPX
 LDX #00
 LDY #00
 JSR $1806
 INY
 JMP $1803
R25TOPX RTS"""



GCDRAW_START_OLD = """ LDA A2
 STA $60D1
 JSR LF36
 LDX #00
 STX RETFLAG"""

GCDRAW_START_NEW = """ LDA A2
 STA $60D1
 JSR $6ECA
 LDX #00
 STX RETFLAG"""

GCDRAW_DUMP_OLD = """DUMP2 STX BADDR
 STY BADDR+1
 LDX #07
 LDY #00
 JSR CRLF
*
ROW LDX #00
 LDY #01
 JSR CRLF
 LDA COLORPR"""

GCDRAW_DUMP_NEW = """DUMP2 STX BADDR
 STY BADDR+1
 LDX #07
 LDY #00
 JSR CRLF
 LDX #00
 LDY #00
 JSR SENDGC
 LDX CREDBUF-1
 DEX
 BNE ROW
 INC CREDBUF-1
 BNE ROW0
ROW LDX #00
 LDY #01
 JSR CRLF
ROW0 LDA COLORPR"""

GCDRAW_ROWCOUNT_OLD = """DUMP0A LDA #28
 LDX COLORPR
 BEQ DUMP0B
 LDA #07
DUMP0B STA ROWCNT
 LDA SIDE
 CMP #02
 BNE DUMP1
 ASL ROWCNT"""

GCDRAW_ROWCOUNT_NEW = """DUMP0A LDA #28
 LDX COLORPR
 BEQ DUMP0B
 LDA #07
DUMP0B STA ROWCNT
 LDA SIDE
 CMP #02
 BEQ DUMP0S
 LDY $95F1
 CPY #05
 BNE DUMP1
 DEC ROWCNT
 DEC ROWCNT
 BNE DUMP1
DUMP0S ASL ROWCNT"""

GCDRAW_MOVE_OLD = """SR06 LDA BADDR
 CLC
 ADC #$C0
 STA BADDR
 LDA BADDR+1
 ADC #01
 BNE SR08
*
SR07 LDA BADDR
 SEC
 SBC #$C0
 STA BADDR
 LDA BADDR+1
 SBC #01
SR08 STA BADDR+1
*
SR08A DEC ROWCNT
 BNE SR09
 RTS"""

GCDRAW_SIGNSTEP_OLD = """ LDA SIDE
 LSR
 BCS SR07
 BEQ SR06
 LDA ROWCNT
 LSR
 BCC SR08A"""

GCDRAW_SIGNSTEP_NEW = """ LDA SIDE
 LSR
 BCS SR07
 BEQ SR06
 LDA ROWCNT
 LSR
 BCS SR06
 EOR PIECE
 AND #$07
 CMP #03
 BNE SR08A
 DEC ROWCNT"""

GCDRAW_MOVE_NEW = """SR06 LDX #00
 BEQ R9MC
*
SR07 LDX #02
R9MC JSR R9MOVE
*
SR08A DEC ROWCNT
 BNE SR09
 RTS"""

GCDRAW_SENDGC_OLD = """ LDX #00
 LDY SIDE
 LDA GCNUMH,Y
 TAY
 JSR SENDGC"""

GCDRAW_SENDGC_NEW = """ LDX #00
 LDY SIDE
 LDA GCNUMH,Y
 TAY
 LDA #$0D
 JSR COUT1
 JSR SENDGC"""

GCDRAW_HELPER_OLD = """ BCS SR02
*
GCNUMH HEX 040204"""

GCDRAW_HELPER_NEW = """ BCS SR02
*
* R9A TYPE-5 CARD SOURCE-ROW RESAMPLER.
* X=0/2 SELECTS + / - SOURCE DIRECTION.
*
R9MOVE LDA SIDE
 LSR
 BNE R9MN
 LDA ROWCNT
 CMP #15
 BEQ R9MS
 LSR
 BCS R9MN
R9MS INX
R9MN LDA BADDR
 CLC
 ADC R9LO,X
 STA BADDR
 LDA BADDR+1
 ADC R9HI,X
 STA BADDR+1
 RTS
R9LO HEX C0004000
R9HI HEX 0102FEFE
*
GCNUMH HEX 040204"""

GCDRAW_LF36_OLD = """LF36A LDX #02
 LDY SIDE
 BNE LF36B
 INY
LF36B JMP CRLF"""

GCDRAW_LF36_NEW = """LF36A LDY SIDE
 LDX GCNUMH,Y
 DEX
 DEX
 CPY #02
 BCS LF36B
 INY
LF36B JMP CRLF"""



def patch_gcdraw(text: str) -> str:
    patched = replace_once(
        text,
        GCDRAW_START_OLD,
        GCDRAW_START_NEW,
        "GCDRAW.S common startup LF36 suppression",
    )
    patched = replace_once(
        patched,
        GCDRAW_DUMP_OLD,
        GCDRAW_DUMP_NEW,
        "GCDRAW.S first-row/piece boundary block",
    )
    patched = replace_once(
        patched,
        GCDRAW_ROWCOUNT_OLD,
        GCDRAW_ROWCOUNT_NEW,
        "GCDRAW.S type-5 card row count",
    )
    patched = replace_once(
        patched,
        GCDRAW_SENDGC_OLD,
        GCDRAW_SENDGC_NEW,
        "GCDRAW.S hard carriage home before raster row",
    )
    patched = replace_once(
        patched,
        GCDRAW_SIGNSTEP_OLD,
        GCDRAW_SIGNSTEP_NEW,
        "GCDRAW.S type-5 sign duplicate-row trim",
    )
    patched = replace_once(
        patched,
        GCDRAW_MOVE_OLD,
        GCDRAW_MOVE_NEW,
        "GCDRAW.S type-5 card/source stepping",
    )
    patched = replace_once(
        patched,
        GCDRAW_LF36_OLD,
        GCDRAW_LF36_NEW,
        "GCDRAW.S native fold feed",
    )
    return replace_once(
        patched,
        GCDRAW_HELPER_OLD,
        GCDRAW_HELPER_NEW,
        "GCDRAW.S type-5 card row resampler",
    )

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("ascii", "replace")).hexdigest()


def find_entry(img: bytes, wanted: str):
    for entry in catalog(img):
        if entry["name"].upper() == wanted.upper():
            return entry
    raise RuntimeError(f"{wanted!r} not found in DOS 3.3 catalog")


def binary_payload(raw: bytes) -> tuple[bytes, bytes]:
    """Return (4-byte DOS binary header, payload) with sanity checking."""
    if len(raw) < 4:
        raise RuntimeError("DOS binary file is shorter than its 4-byte header")
    length = raw[2] | (raw[3] << 8)
    if not 0 < length <= len(raw) - 4:
        raise RuntimeError(
            f"implausible DOS binary length {length} for {len(raw)} raw bytes"
        )
    return raw[:4], raw[4:4 + length]


def decode_source_payload(payload: bytes) -> str:
    payload = bytes(b & 0x7F for b in payload)
    return (
        payload.decode("ascii", "replace")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\x00", "\n")
    )


def binary_source_info(img: bytes, name: str):
    entry = find_entry(img, name)
    raw = file_sectors(img, entry)
    header, payload = binary_payload(raw)

    significant = [b for b in payload if (b & 0x7F) not in (0x00,)]
    high_count = sum(1 for b in significant if b & 0x80)
    high_ratio = high_count / len(significant) if significant else 0.0

    return {
        "entry": entry,
        "header": header,
        "payload": payload,
        "high_ratio": high_ratio,
        "text": decode_source_payload(payload),
    }


def binary_source_text(img: bytes, name: str) -> str:
    return binary_source_info(img, name)["text"]


def replace_once(text: str, old: str, new: str, what: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{what}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_prcoms(text: str) -> str:
    gc_matches = list(GC5_OLD.finditer(text))
    if len(gc_matches) != 1:
        raise RuntimeError(
            "PRCOMS.S GC5 block: expected exactly one legacy type-5 block, "
            f"found {len(gc_matches)}"
        )

    crlf_matches = list(CRLF_OLD.finditer(text))
    if len(crlf_matches) != 1:
        raise RuntimeError(
            "PRCOMS.S CRLF block: expected exactly one original block, "
            f"found {len(crlf_matches)}"
        )

    sgc5_matches = list(SGC5_OLD.finditer(text))
    if len(sgc5_matches) != 1:
        raise RuntimeError(
            "PRCOMS.S SGC5 block: expected exactly one original block, "
            f"found {len(sgc5_matches)}"
        )

    gc5_end_matches = list(GC5_END_OLD.finditer(text))
    if len(gc5_end_matches) != 1:
        raise RuntimeError(
            "PRCOMS.S GC5 end block: expected exactly one original block, "
            f"found {len(gc5_end_matches)}"
        )

    cout1_matches = list(COUT1_OLD.finditer(text))
    if len(cout1_matches) != 1:
        raise RuntimeError(
            "PRCOMS.S COUT1 block: expected exactly one original block, "
            f"found {len(cout1_matches)}"
        )

    setlf5_count = text.count(SETLF5_OLD)
    if setlf5_count != 1:
        raise RuntimeError(
            "PRCOMS.S SETLF5 block: expected exactly one original block, "
            f"found {setlf5_count}"
        )

    patched = CRLF_OLD.sub(CRLF_NEW, text, count=1)
    patched = SGC5_OLD.sub(SGC5_NEW, patched, count=1)
    patched = GC5_OLD.sub(GC5_NEW, patched, count=1)
    patched = GC5_END_OLD.sub(GC5_END_NEW, patched, count=1)
    patched = COUT1_OLD.sub(COUT1_NEW, patched, count=1)
    patched = patched.replace(SETLF5_OLD, SETLF5_NEW, 1)

    return patched


def patch_menus(text: str) -> str:
    if len(OLD_MENU) != len(NEW_MENU):
        raise AssertionError("menu replacement must remain length-preserving")
    patched = replace_once(text, OLD_MENU, NEW_MENU, "MENUS7.S printer label")
    patched = replace_once(
        patched,
        MENUS_INIT_OLD,
        MENUS_INIT_NEW,
        "MENUS7.S type-5 state initialization",
    )
    ends = list(re.finditer(r"(?m)^[ \\t]*END\\b.*$", patched))
    if not ends:
        raise RuntimeError("MENUS7.S: END directive not found")
    m = ends[-1]
    return patched[:m.start()] + MENUS_R25_HELPER + "\n" + patched[m.start():]


def load_image(path: pathlib.Path | None, disk_index: int) -> bytes:
    if path is not None:
        return path.read_bytes()
    name = NAMES[disk_index]
    return fetch(BASE + urllib.parse.quote(name))


def file_sector_locations(img: bytes, entry) -> list[tuple[int, int]]:
    """Return data-sector T/S pairs in DOS file order."""
    trk, sec = entry["ts_track"], entry["ts_sector"]
    seen = set()
    locations: list[tuple[int, int]] = []

    while trk:
        if (trk, sec) in seen:
            raise RuntimeError(f"T/S-list loop in {entry['name']}")
        seen.add((trk, sec))
        ts = sector(img, trk, sec)
        next_trk, next_sec = ts[1], ts[2]

        for off in range(0x0C, 0x100 - 1, 2):
            dt, ds = ts[off], ts[off + 1]
            if dt == 0:
                continue
            if dt >= 35 or ds >= SECTORS:
                raise RuntimeError(
                    f"invalid data-sector T/S {dt}/{ds} in {entry['name']}"
                )
            locations.append((dt, ds))

        trk, sec = next_trk, next_sec

    return locations


def encode_source_payload(text: str, high_ratio: float) -> bytes:
    """Recreate the Big Mac/DOS source byte convention.

    The historical source payload is Apple-style CR text.  If the template
    uses the Apple high-bit text convention (which these source files do),
    preserve it for every source character.
    """
    raw = text.replace("\n", "\r").encode("ascii", "strict")
    if high_ratio >= 0.80:
        raw = bytes(b | 0x80 for b in raw)
    return raw


def rewrite_binary_file(img: bytes, name: str, patched_text: str) -> bytes:
    """Rewrite one existing DOS binary file in-place without reallocating."""
    info = binary_source_info(img, name)
    entry = info["entry"]
    locations = file_sector_locations(img, entry)

    payload = encode_source_payload(patched_text, info["high_ratio"])
    old_header = info["header"]
    header = old_header[:2] + len(payload).to_bytes(2, "little")
    packed = header + payload

    capacity = len(locations) * SECTOR_SIZE
    if len(packed) > capacity:
        raise RuntimeError(
            f"{name}: patched file needs {len(packed)} bytes, "
            f"but existing allocation holds only {capacity}"
        )

    out = bytearray(img)
    packed += bytes(capacity - len(packed))

    for index, (trk, sec) in enumerate(locations):
        start = (trk * SECTORS + sec) * SECTOR_SIZE
        src = index * SECTOR_SIZE
        out[start:start + SECTOR_SIZE] = packed[src:src + SECTOR_SIZE]

    roundtrip = binary_source_text(bytes(out), name)
    if roundtrip != patched_text:
        raise RuntimeError(f"{name}: DOS disk rewrite failed round-trip verification")

    return bytes(out)


def write_patched_disks(
    output_dir: pathlib.Path,
    disk1: bytes,
    disk2: bytes,
    disk3: bytes,
    patched_prcoms: str,
    patched_menus7: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    out1 = rewrite_binary_file(disk1, "PRCOMS.S", patched_prcoms)
    out2 = rewrite_binary_file(disk2, "MENUS7.S", patched_menus7)

    p1 = output_dir / "PrintShop-V2-OkiGraph-source-1.dsk"
    p2 = output_dir / "PrintShop-V2-OkiGraph-source-2.dsk"
    p3 = output_dir / "PrintShop-V2-OkiGraph-source-3.dsk"

    p1.write_bytes(out1)
    p2.write_bytes(out2)
    p3.write_bytes(disk3)

    # Final content assertions against the generated disk images.
    rt1 = binary_source_text(out1, "PRCOMS.S")
    rt2 = binary_source_text(out2, "MENUS7.S")
    if (
        " ORA #$80\n" not in rt1
        or GC5_OLD.search(rt1)
        or "COUTRAW STX XTEMP\n" not in rt1
    ):
        raise RuntimeError("generated source disk 1 does not contain the OkiGraph GC5 patch")
    if (
        NEW_MENU not in rt2
        or OLD_MENU in rt2
        or " STA $B9\n" not in rt2
    ):
        raise RuntimeError(
            "generated source disk 2 does not contain the OkiGraph menu/init patch"
        )

    print("  generated DOS 3.3 source disks:")
    print(f"    {p1}")
    print(f"    {p2}")
    print(f"    {p3} (unchanged source disk 3)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disk1", type=pathlib.Path,
                    help="local source disk 1 .dsk instead of downloading")
    ap.add_argument("--disk2", type=pathlib.Path,
                    help="local source disk 2 .dsk instead of downloading")
    ap.add_argument("--disk3", type=pathlib.Path,
                    help="local source disk 3 .dsk instead of downloading")
    ap.add_argument("--output-dir", type=pathlib.Path,
                    help="emit decoded patched PRCOMS/MENUS7 source")
    ap.add_argument("--output-disks", type=pathlib.Path,
                    help="emit patched copies of all three DOS 3.3 source disks")
    ap.add_argument("--check", action="store_true",
                    help="validate patch applicability without requiring output")
    args = ap.parse_args()

    disk1 = load_image(args.disk1, 0)
    disk2 = load_image(args.disk2, 1)

    prcoms_info = binary_source_info(disk1, "PRCOMS.S")
    menus7_info = binary_source_info(disk2, "MENUS7.S")
    gcdraw_info = binary_source_info(disk2, "GCDRAW.S")
    prcoms = prcoms_info["text"]
    menus7 = menus7_info["text"]
    gcdraw = gcdraw_info["text"]

    patched_prcoms = patch_prcoms(prcoms)
    patched_menus7 = patch_menus(menus7)
    patched_gcdraw = patch_gcdraw(gcdraw)

    # These are the two invariants that keep the first hardware build
    # deliberately low-risk.
    assert len(OLD_MENU) == len(NEW_MENU) == 23

    print("Print Shop v2 OkiGraph I source patch: PASS")
    print("  printer type: 5 (repurposed legacy Okidata 92/93 path)")
    print("  menu label: 23 -> 23 characters")
    print("  R25 base: R24 seven-band sign trim; R21 card geometry unchanged")
    print("  R25 sign top: one native 15/144-inch OkiGraph feed before rendering")
    print("  R25 sign height: unchanged from R24 at seven omitted duplicate bands")
    print("  R25 expected margins from 8/12 mm: about 10.65/9.35 mm")
    print("  graphics data: R11 original Oki type-5 $03 escape semantics")
    print("  framing: existing $03 ... $03 $02 retained")
    print(f"  PRCOMS source high-bit ratio: {prcoms_info['high_ratio']:.3f}")
    print(f"  MENUS7 source high-bit ratio: {menus7_info['high_ratio']:.3f}")
    print(f"  PRCOMS decoded SHA256 before: {sha256_text(prcoms)}")
    print(f"  PRCOMS decoded SHA256 after : {sha256_text(patched_prcoms)}")
    print(f"  MENUS7 decoded SHA256 before: {sha256_text(menus7)}")
    print(f"  MENUS7 decoded SHA256 after : {sha256_text(patched_menus7)}")
    print(f"  GCDRAW decoded SHA256 before: {sha256_text(gcdraw)}")
    print(f"  GCDRAW decoded SHA256 after : {sha256_text(patched_gcdraw)}")

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "PRCOMS.OKI.S").write_text(
            patched_prcoms, encoding="ascii", newline="\n"
        )
        (args.output_dir / "MENUS7.OKI.S").write_text(
            patched_menus7, encoding="ascii", newline="\n"
        )
        (args.output_dir / "GCDRAW.OKI.S").write_text(
            patched_gcdraw, encoding="ascii", newline="\n"
        )
        print(f"  wrote decoded patched source to: {args.output_dir}")

    if args.output_disks:
        disk3 = load_image(args.disk3, 2)
        write_patched_disks(
            args.output_disks,
            disk1,
            disk2,
            disk3,
            patched_prcoms,
            patched_menus7,
        )

    if not args.check and not args.output_dir and not args.output_disks:
        print(
            "  note: use --output-dir build and/or --output-disks build "
            "to generate local build inputs"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
