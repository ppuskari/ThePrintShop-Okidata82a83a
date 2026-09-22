# The Print Shop – Okidata MICROLINE 82A/83A OkiGraph I Driver

Apple II printer-driver work for **Brøderbund The Print Shop v2**, targeting
the **Okidata MICROLINE 82A and 83A with OkiGraph I firmware**.

## Current status

**R17 fine vertical card-centering experiment: CI-validated; hardware measurement is next.**

The original Print Shop v2 source already contains a dedicated
`OKIDATA MICROLINE 92,93` printer type. That path is an unusually good
starting point for the 82A/83A OkiGraph I driver because it already:

- converts the application's 120-column/inch graphics stream to a
  60-column/inch Okidata stream by merging source-column pairs;
- reverses the lower seven graphics bits for Okidata pin order;
- enters graphics with `$03`;
- leaves graphics with `$03 $02`; and
- uses Okidata `ESC % 9 n` programmable line spacing.

The v0.1 driver deliberately repurposes that printer type instead of adding
a tenth selector immediately.

The hardware-good R11 graphics-byte conversion is:

```
logical = reverse7(source0 | source1)

normal logical byte -> send once
logical $03         -> send $03,$03
```

The doubled-ETX rule restores the historical Okidata type-5 literal-data
escape and eliminated the progressive horizontal column loss seen in earlier
builds.

## R17 fine vertical card centering

R17 uses the perforation-defined R14 paper-position test plus the R16
caliper measurements to move the greeting-card geometry in deliberately
small 1/144-inch increments.

The important correction is that OkiGraph's historical `ESC % 9 n`
programmable spacing is valid in text mode.  Earlier experiments sent that
sequence while the printer was still in OkiGraph graphics state.  R17
therefore restores the historical type-5 `SETLF5` implementation, while
the type-5 `CRLF` path continues using native `$03 $0E` feeds whenever
`FIX80` says graphics mode is active.  If a nonzero-X boundary call exits
graphics, it then falls through to the normal text-mode spacing path.

The top-of-card adjustment is:

```text
R16 startup:  30/144 in = two native graphics feeds
R17 startup:   4/144 in = restored LF36 through ESC %9
              15/144 in = one native graphics feed
              ---------
              19/144 in total

R17 moves the top upward by 11/144 in = 1.940 mm.
```

At the normal `X=12` card-piece boundary, type 5 now uses `X=17`.
Because `SETLF5` converts X/72-inch units to the Oki `n/144` value, that
changes the boundary feed from 24/144 to 34/144 inch: an additional
**10/144 inch = 1.764 mm** between vertical card panels.  Relative to R16,
the lower panel therefore moves only 1/144 inch (0.176 mm) upward even though
the top panel gains almost 2 mm of top margin.

The end-of-card correction uses the two existing DOALL9 calls rather than
adding another code path.  The restored LF36 contributes 4/144 inch, and the
type-5 `X=12,Y=0` final boundary is normalized to `X=4,Y=1`, contributing
another 8/144 inch.  Together with the 10/144-inch increase after the second
panel, the end position advances by exactly:

```text
10/144 + 4/144 + 8/144 = 22/144 inch
                         = 3.881 mm
```

That directly targets the measured 3.8-3.9 mm shortfall to the next
perforation.

The `X=12` normalization is inside the printer-type-5 branch only; other
printer types do not receive those fine-spacing substitutions.  R17 does
restore the original GCDRAW startup `JSR LF36` that R12 had globally
suppressed, so non-type-5 printers return to the historical Print Shop
startup behavior.

R17 also removes the redundant `JMP SR08A` after `JSR R9MOVE`; execution
already falls directly into `SR08A`.  This pays for the restored startup
call without expanding DRAW1.

Validated R17 overlays:

```text
PRCOMS.OKI
length 2044
SHA256 4861589b0480a3ea47d3b2913b179e7730f668f47b25e862898578071a57a678

GCDRAW.OKI -> runtime DRAW1
length 2808
SHA256 140eab8c13a87c93fcc6cbfe622d1e3e5799de32ab9d1b89e93bdeb5f57c5ef0

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

Validated R17 runtime image:

```text
size   143360 bytes
SHA256 2eef4359713ac807e1795105625ecafa2324a20fc72bc01fd61fe4c7995a8731
```

PRCOMS's 2044-byte payload plus the four-byte DOS binary header exactly fills
its existing 2048-byte on-disk allocation.  DRAW1 remains comfortably below
the `$8300` application-data boundary.  The R14 CR-only TEST PAPER POSITION
patch, graphics-byte escaping, source-row resampling, and horizontal geometry
are unchanged.

## R16 first-card raster: two native OkiGraph feeds

With R15 aligned from the perforation-defined paper-position test, hardware
measurement put the top border dots at about 5.4 mm and the bottom border dots
at about 11.2-11.4 mm.  Centering that image requires roughly another 2.9-3.0
mm downward shift.  One native OkiGraph graphics feed is about 15/144 inch,
or 2.65 mm, so R16 tests exactly one additional native feed.

The first physical card raster now takes `CRLF X=0,Y=2` while graphics mode
is already active.  On the OkiGraph-specific PRCOMS path that produces two
native graphics advances before the first raster:

```text
$03 $0E
$03 $0E
```

Normal later rows still use `Y=1`, so their spacing is unchanged.  No text
line feed is restored.

To fit this without crossing the Print Shop application-data boundary at
`$8300`, the first-raster decision is written as a four-byte extension only:

```asm
R13FIRST LDA PIECE
 CLC
 ADC YMAX
 CMP #$88
 BNE ROW
 LDY #02
 BNE R16ROW
*
ROW LDX #00
 LDY #01
R16ROW JSR CRLF
ROW0 LDA COLORPR
```

On the first-pane condition, X is already zero from `LDX CREDBUF-1 / BEQ`,
so the special path can skip `LDX #00`.  `LDY #02` clears Z, making the
`BNE R16ROW` unconditional.  Other cases fall through the normal
`LDX #00 / LDY #01` row path.

The runtime DRAW1 DOS file has an existing 2816-byte on-disk allocation,
but four of those bytes are the DOS binary load/length header, so the maximum
payload that can be rewritten in place is 2812 bytes.  R16 therefore recovers
four bytes elsewhere instead of growing the file:

- the three R12 padding NOPs that replaced the removed startup `JSR LF36`
  are now omitted entirely; all labels are reassembled, so they are not needed
  for layout preservation;
- immediately after `INC CREDBUF-1`, `JMP ROW0` becomes `BNE ROW0`.
  That branch is guaranteed taken on this path because the preceding logic
  reaches it only when `CREDBUF-1` was 1, so the increment produces 2.

Those four bytes exactly pay for the R16 two-feed first-raster logic.  The
assembled GCDRAW/DRAW1 payload remains 2812 bytes and still fits the existing
DOS allocation without reallocating sectors.  PRCOMS, MENUS7, source-row
resampling, fold and inter-piece geometry, graphics escaping, and the R14
CR-only paper-position patch are unchanged.

## R15 first-card raster: one native OkiGraph feed

The perforation-aligned R14 paper-position test removed the remaining setup
ambiguity.  Hardware comparison showed that the current zero-feed first raster
starts slightly too high, while one manual normal line feed starts clearly too
low.

R15 changes only the R13 first-physical-card-raster branch.  When the
`PIECE + YMAX = $88` first-pane condition is true, execution now goes through
the existing `ROW` path instead of skipping directly to `ROW0`:

```asm
; R13
CMP #$88
BEQ ROW0

; R15
CMP #$88
BEQ ROW
```

For printer type 5, graphics mode has already been entered by `SENDGC`.
The existing `ROW` call uses `CRLF X=0,Y=1`, which the OkiGraph-specific
PRCOMS path implements as exactly one native graphics feed:

```text
$03 $0E
```

That is the roughly 15/144-inch startup shift we want to test.  No normal
text LF is restored.  PRCOMS, graphics escaping, source-row resampling, later
raster feeds, fold spacing, inter-piece positioning, and the R14 CR-only paper
alignment patch are unchanged.

The source edit is length-preserving: the assembled GCDRAW/DRAW1 overlay
remains 2812 bytes and only the relative branch target changes.

## R14 TEST PAPER POSITION: carriage return only

The original Print Shop `TEST PAPER POSITION` path prints its horizontal
alignment dots and then advances the paper.  Source/runtime tracing shows that
DRAW5 menu option 2 calls SYSLIB through `$8803`.  SYSLIB's routine at
`$88CC` ends at `$88FA` with:

```asm
INX
LDY #$01
JMP $1803       ; PRCOMS CRLF
```

That final jump is the unwanted carriage-return/line-feed operation.  R14
changes only that six-byte epilogue, leaving the dot pattern, printer driver,
and every normal print-path CR/LF untouched:

```asm
LDA #$0D
JMP $1800       ; raw printer character output: CR only
NOP             ; length-preserving runtime patch
```

Runtime bytes at `SYSLIB $88FA`:

```text
original  E8 A0 01 4C 03 18
R14       A9 0D 4C 00 18 EA
```

The runtime builder refuses to apply the patch unless SYSLIB loads at
`$8800` and the exact six historical bytes are present.  It then rereads
SYSLIB through the DOS T/S chain and verifies the complete patched payload.
This makes repeated paper-position tests return the carriage to column zero
without changing the paper's vertical position, so the operator can
micro-adjust the fanfold paper and run the test again.

## R13 first-pane top alignment

R13 keeps the hardware-good R11 OkiGraph driver and the R12 common startup
`LF36` removal unchanged.  Hardware testing of R12 showed one remaining
full first-row feed before the physically first greeting-card pane when the
paper top is aligned with the top print-head pin.

The first inside-card pass satisfies `PIECE + YMAX = 392` for both
monochrome and color, so R13 uses that geometry to suppress only that first
`ROW` CRLF while `CREDBUF-1` is still in its initial state.  The existing
outside-card first-row suppression, all later raster-row feeds, fold spacing,
and inter-piece positioning remain unchanged.

Validated R13 runtime image:

```
size   143360 bytes
SHA256 3eef3ef4660483bce6681f939fc3f1409ac533319efc9d332407e0c57c152bc1
```

Validated R13 overlays:

```
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485

GCDRAW.OKI -> runtime DRAW1
length 2812
SHA256 2c37296b3e8d4bdad9170c0b56be91cc29925a9089e975d406efb2e9643e8bf9
```

## R12 common startup-feed cleanup

R12 keeps the hardware-good R11 OkiGraph driver unchanged and modifies only
the common greeting-card/sign drawing overlay.

Historical `GCDRAW` begins the print job with:

```
JSR LF36
```

before the drawing path performs its own first-row positioning.  That produces
two stacked startup vertical motions and affects every printer type using the
same base program path, including Epson, DMP/ImageWriter, ImageWriter II, and
Okidata.

R12 replaces only that initial three-byte `JSR LF36` with three `NOP`
instructions.  End-of-job, fold, and inter-piece positioning remain unchanged.

Validated R12 runtime image:

```
size   143360 bytes
SHA256 4259a5e98464f32e1aec691ae3365d21e471ceb585a12ee5ec54be4b8175ac0d
```

Validated R12 overlays:

```
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485

GCDRAW.OKI -> runtime DRAW1
length 2807
SHA256 46a9e2c6777a4da7d96cceabdbb5c7246421067bf2b529410a99bb9b0e406011
```

## R11 horizontal-stream test

R11 keeps the R10/R9A geometry and changes only the type-5 graphics-data
escaping. The historical Oki type-5 path emits seven-bit graphics bytes
directly and doubles a literal ETX (`$03`) as `$03,$03`. Earlier OkiGraph
builds forced bit 7 instead (`$83`), which is now under hardware test as a
possible source of mid-row column loss if the printer parser treats graphics
data as seven-bit.

Validated R11 runtime image:

```
size   143360 bytes
SHA256 1a40ea0430d472635279ff1bc9a3125e64def52ef0973f02ad1d19532884f830
```

Validated R11 PRCOMS overlay:

```
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137
```

## Driver evolution

The initial v0.1 patch was deliberately layout-preserving and proved the
graphics-data path on real hardware.  R3 keeps the fixed `PRCOMS` jump table
at `$1800`, leaves Print Shop's printer-interface-card code untouched, and
retains the proven high-bit-safe raster conversion.  The type-5 CR/LF control
path is now OkiGraph-specific because hardware testing disproved reuse of the
legacy ML92/93 spacing sequence.

The assembly/control notes are in [`src/OKI8283.S`](src/OKI8283.S).

## Runnable disk build

The historical sources now assemble into real executable overlays with
Merlin32. An untouched control build was compared against the archived
`ColorPrintShop.DSK` runtime:

- `PRCOMS`: 1,962 bytes, exact byte-for-byte match, load address `$1800`
- `MENUS7`: 3,014 bytes, exact byte-for-byte match, load address `$6300`

That establishes a compatible runtime base for this source snapshot.

To build the actual runnable disk on Windows:

```powershell
.\scripts\Build-RuntimeDisk.ps1
```

It creates:

```
build-runtime\PrintShop-Okidata82a83a-OkiGraphI.dsk
```

Current R17 validated image:

```
size   143360 bytes
SHA256 2eef4359713ac807e1795105625ecafa2324a20fc72bc01fd61fe4c7995a8731
```

R6 was physically validated and was the closest result yet: the total vertical
size was within roughly half an inch, but literal control-sequence fragments
still appeared at the start/midpoint/end, several border motifs lost their
lower portion near the right edge, and two card quadrants showed localized
raster corruption.

The R6 sheet proved that the inherited ML92/93 `ESC % 9 n` sequence must not
be used on this OkiGraph-I path. R7 removes it completely and returns to the
hardware-proven R5 continuous-graphics core. Type-5 state is initialized when
the printer is selected. Normal in-graphics rows remain `$03 $0E`; X=12
boundary motion uses ordinary 1/6-inch LF; and Print Shop's X=2 LF36 helper is
suppressed rather than being incorrectly expanded to a full LF.

Greeting-card source tracing also confirmed that GCDRAW uses fixed even
`SENDGC` sizes (`$0200`/`$0400`), so the observed right-edge card defect
is not caused by variable blank trimming or an odd transaction count.

Validated R7 overlays:

```
PRCOMS.OKI
length 2034
SHA256 a960e7c6a92003f4a7cc42dda5db75b433d75abb4adfb30d40bc30c156f68124

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

PRCOMS remains entirely below the Apple II `$2000` boundary.

The script uses an installed Merlin32 if available; otherwise it downloads
the pinned v1.1.10 Windows build. It verifies the original runtime overlays
against the control build before changing the disk, then rewrites only
`PRCOMS` and `MENUS7` through their existing DOS T/S chains and verifies
both files after read-back.

See [`docs/EXECUTABLE-BUILD.md`](docs/EXECUTABLE-BUILD.md) for the complete
reproducibility and validation record.

## Build / validate on Windows

From the repository root:

```powershell
.\scripts\Build-DriverSource.ps1
```

That performs the wire-model unit tests, checks the patch against the actual
1987 Print Shop v2 source snapshot, and produces decoded patched source plus
a complete three-disk local source set:

```
build\PRCOMS.OKI.S
build\MENUS7.OKI.S
build\PrintShop-V2-OkiGraph-source-1.dsk
build\PrintShop-V2-OkiGraph-source-2.dsk
build\PrintShop-V2-OkiGraph-source-3.dsk
```

Equivalent individual commands:

```powershell
py -3 -m unittest discover -s tests -v
py -3 tools\patch_printshop_source.py --check
py -3 tools\patch_printshop_source.py --output-dir build --output-disks build
```

Source disks 1 and 2 contain the rewritten files; source disk 3 is copied
unchanged so the build directory contains a complete set. The historical
Brøderbund source and generated disk images are **not committed to this repository**.

## Validation status

GitHub Actions currently verifies:

- seven-bit reversal;
- 120-to-60 column conversion;
- bit 7 set on every graphics-data byte;
- the legacy raw-`$03` collision becomes `$83`;
- OkiGraph transaction framing;
- R3 text and graphics CR/LF framing, including the mandatory Y=0 carriage return; and
- exact applicability of the source patch to the 1987-01-26 source disks;
- DOS source-disk rewrite/read-back through the original T/S chains;
- untouched Merlin32 control overlays against the shipped runtime;
- patched executable overlay sizes and hashes;
- in-place runtime-disk replacement with preserved load addresses; and
- the complete Windows build producing a deterministic 143,360-byte `.dsk`.

## Repository map

- `src/OKI8283.S` — 6502 assembly integration fragment
- `src/driver_model.py` — executable wire-level model
- `tools/patch_printshop_source.py` — source transformation
- `tools/prepare_merlin32_build.py` — Big Mac-to-Merlin32 build preparation
- `tools/validate_overlay_build.py` — control/patched executable verification
- `tools/build_runtime_disk.py` — verified executable disk construction
- `tools/inspect_printshop_source.py` — reproducible historical-source scanner
- `tests/test_driver_model.py` — regression tests
- `docs/DESIGN.md` — source/driver architecture and design decisions
- `docs/EXECUTABLE-BUILD.md` — executable overlay/runtime-disk build record
- `docs/HARDWARE-TEST.md` — staged 82A/83A physical validation plan
- `scripts/Build-DriverSource.ps1` — source-disk build helper
- `scripts/Build-RuntimeDisk.ps1` — one-command executable `.dsk` build

## Source basis

Print Shop v2 interface discovery uses the three-disk source snapshot dated
**1987-01-26** from the Asimov Apple II archive.

OkiGraph I protocol behavior is based on the independent ROM reconstruction
and hardware work in:

https://github.com/ppuskari/Okidata-Microline-82A-83A

## Next milestone

Measure the R17 greeting-card output on physical OkiGraph-equipped ML82A/83A
hardware from an R14 perforation-aligned start.  Record top border-to-
perforation distance, the vertical panel gap, bottom border-to-perforation
distance, and the post-print TEST PAPER POSITION dot offset at the next
perforation.

After card geometry is frozen, validate signs and stationery, then restore the
stock Okidata 92/93 menu entry and add **82A/83A OkiGraph I** as a distinct
printer selection.
